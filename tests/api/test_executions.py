import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from safeexec.adapters.metrics import get_metrics
from safeexec.api.v1.executions import get_execution_service
from safeexec.domain.concurrency import ConcurrencyLimiter
from safeexec.domain.errors import SandboxUnavailableError
from safeexec.domain.limits import LimitsPolicy
from safeexec.domain.service import ExecutionService
from safeexec.main import create_app
from safeexec.models import MAX_CODE_CHARS
from tests.fakes import FakeSandbox, InMemoryExecutionRepository

VALID_PAYLOAD = {"language": "python", "code": "print('hello')"}

RESULT_FIELDS = {
    "id", "language", "stdout", "stderr", "exit_code", "duration_ms",
    "timed_out", "oom_killed", "stdout_truncated", "stderr_truncated", "created_at",
}  # fmt: skip


def _app_with(service: ExecutionService) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_execution_service] = lambda: service
    return application


async def test_valid_post_returns_complete_result(client: AsyncClient) -> None:
    response = await client.post("/v1/executions", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESULT_FIELDS
    assert body["stdout"] == "hello\n"
    assert body["exit_code"] == 0


async def test_unknown_language_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/v1/executions", json={"language": "rust", "code": "fn main(){}"})
    assert response.status_code == 422


async def test_oversized_code_is_rejected(client: AsyncClient) -> None:
    payload = {"language": "python", "code": "x" * (MAX_CODE_CHARS + 1)}
    response = await client.post("/v1/executions", json=payload)
    assert response.status_code == 422


async def test_unexpected_fields_are_rejected(client: AsyncClient) -> None:
    response = await client.post("/v1/executions", json={**VALID_PAYLOAD, "shell": "bash"})
    assert response.status_code == 422


async def test_out_of_range_limits_return_actionable_422(client: AsyncClient) -> None:
    payload = {**VALID_PAYLOAD, "limits": {"timeout_ms": 999_999}}
    response = await client.post("/v1/executions", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "timeout_ms" in detail
    assert "must be between" in detail


async def test_idempotent_retry_returns_same_result_without_reexecuting(
    client: AsyncClient, fake_sandbox: FakeSandbox
) -> None:
    payload = {**VALID_PAYLOAD, "client_request_id": "retry-1"}

    first = await client.post("/v1/executions", json=payload)
    second = await client.post("/v1/executions", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(fake_sandbox.calls) == 1


async def test_capacity_exhaustion_returns_429(
    limits_policy: LimitsPolicy, repository: InMemoryExecutionRepository
) -> None:
    release = asyncio.Event()
    sandbox = FakeSandbox(release=release)
    service = ExecutionService(
        sandbox=sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
    )
    transport = ASGITransport(app=_app_with(service))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        blocked = asyncio.create_task(client.post("/v1/executions", json=VALID_PAYLOAD))
        while not sandbox.calls:
            await asyncio.sleep(0)

        rejected = await client.post("/v1/executions", json=VALID_PAYLOAD)
        assert rejected.status_code == 429
        assert rejected.headers["retry-after"] == "1"

        release.set()
        assert (await blocked).status_code == 200


async def test_sandbox_unavailable_returns_503_without_internals(
    limits_policy: LimitsPolicy, repository: InMemoryExecutionRepository
) -> None:
    sandbox = FakeSandbox(error=SandboxUnavailableError("docker daemon exploded at /var/run"))
    service = ExecutionService(
        sandbox=sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
    )
    transport = ASGITransport(app=_app_with(service))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/executions", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "docker" not in response.json()["detail"].lower()


async def test_metrics_endpoint_exposes_execution_counters(
    limits_policy: LimitsPolicy, repository: InMemoryExecutionRepository
) -> None:
    service = ExecutionService(
        sandbox=FakeSandbox(),
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
        metrics=get_metrics(),
    )
    transport = ASGITransport(app=_app_with(service))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/v1/executions", json=VALID_PAYLOAD)
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert 'safeexec_executions_total{language="python",outcome="success"}' in response.text
    assert "safeexec_execution_duration_seconds" in response.text
