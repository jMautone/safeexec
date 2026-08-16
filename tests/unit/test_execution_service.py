import asyncio

import pytest

from safeexec.domain.concurrency import ConcurrencyLimiter
from safeexec.domain.errors import CapacityExceededError, LimitsOutOfRangeError
from safeexec.domain.limits import LimitsPolicy
from safeexec.domain.sandbox import SandboxResult
from safeexec.domain.service import ExecutionService
from safeexec.models import ExecutionRequest, Language, LimitOverrides
from tests.fakes import FakeSandbox, InMemoryExecutionRepository

REQUEST = ExecutionRequest(language=Language.PYTHON, code="print('hello')")


async def test_success_is_persisted_and_returned(
    service: ExecutionService,
    fake_sandbox: FakeSandbox,
    repository: InMemoryExecutionRepository,
) -> None:
    execution = await service.execute(REQUEST)

    assert execution.stdout == "hello\n"
    assert execution.exit_code == 0
    assert execution.timed_out is False
    assert execution.oom_killed is False
    assert repository.executions == [execution]
    assert fake_sandbox.calls[0].code == "print('hello')"


async def test_sandbox_receives_resolved_limits(
    service: ExecutionService, fake_sandbox: FakeSandbox
) -> None:
    request = ExecutionRequest(
        language=Language.PYTHON,
        code="print(1)",
        overrides=LimitOverrides(timeout_ms=10_000),
    )
    await service.execute(request)

    limits = fake_sandbox.calls[0].limits
    assert limits.timeout_ms == 10_000
    assert limits.memory_mb == 128


@pytest.mark.parametrize(
    ("result_kwargs", "field"),
    [
        ({"timed_out": True, "exit_code": None}, "timed_out"),
        ({"oom_killed": True, "exit_code": 137}, "oom_killed"),
        ({"stdout_truncated": True}, "stdout_truncated"),
        ({"stderr_truncated": True}, "stderr_truncated"),
    ],
)
async def test_failure_modes_are_modeled_as_results(
    repository: InMemoryExecutionRepository,
    limits_policy: LimitsPolicy,
    result_kwargs: dict[str, object],
    field: str,
) -> None:
    base = {
        "stdout": "",
        "stderr": "",
        "exit_code": 1,
        "duration_ms": 5_000,
        "timed_out": False,
        "oom_killed": False,
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    sandbox = FakeSandbox(result=SandboxResult(**{**base, **result_kwargs}))  # type: ignore[arg-type]
    service = ExecutionService(
        sandbox=sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
    )

    execution = await service.execute(REQUEST)

    assert getattr(execution, field) is True


async def test_out_of_range_limits_are_rejected_before_running(
    service: ExecutionService, fake_sandbox: FakeSandbox
) -> None:
    request = ExecutionRequest(
        language=Language.PYTHON,
        code="print(1)",
        overrides=LimitOverrides(memory_mb=10_000),
    )
    with pytest.raises(LimitsOutOfRangeError):
        await service.execute(request)
    assert fake_sandbox.calls == []


async def test_same_client_request_id_replays_without_reexecuting(
    service: ExecutionService, fake_sandbox: FakeSandbox
) -> None:
    request = ExecutionRequest(language=Language.PYTHON, code="print(1)", client_request_id="req-1")

    first = await service.execute(request)
    second = await service.execute(request)

    assert second == first
    assert len(fake_sandbox.calls) == 1


async def test_capacity_exceeded_when_all_slots_busy(
    repository: InMemoryExecutionRepository, limits_policy: LimitsPolicy
) -> None:
    release = asyncio.Event()
    sandbox = FakeSandbox(release=release)
    service = ExecutionService(
        sandbox=sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
    )

    running = asyncio.create_task(service.execute(REQUEST))
    while not sandbox.calls:
        await asyncio.sleep(0)

    with pytest.raises(CapacityExceededError):
        await service.execute(REQUEST)

    release.set()
    await running


async def test_metrics_record_language_and_outcome(
    fake_sandbox: FakeSandbox,
    repository: InMemoryExecutionRepository,
    limits_policy: LimitsPolicy,
) -> None:
    recorded: list[tuple[str, str, int]] = []

    class SpyMetrics:
        def record(self, language: str, outcome: str, duration_ms: int) -> None:
            recorded.append((language, outcome, duration_ms))

    service = ExecutionService(
        sandbox=fake_sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(1),
        metrics=SpyMetrics(),
    )
    await service.execute(REQUEST)

    assert recorded == [("python", "success", 12)]
