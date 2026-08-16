"""Execution service: idempotency → limits → bounded sandbox run → persisted result."""

import uuid
from datetime import UTC, datetime

from safeexec.domain.concurrency import ConcurrencyLimiter
from safeexec.domain.limits import LimitsPolicy
from safeexec.domain.metrics import ExecutionMetrics, NullMetrics
from safeexec.domain.repository import ExecutionRepository
from safeexec.domain.sandbox import Sandbox, SandboxResult, SandboxSpec
from safeexec.models import Execution, ExecutionRequest


def _outcome(result: SandboxResult) -> str:
    if result.timed_out:
        return "timeout"
    if result.oom_killed:
        return "oom"
    return "success" if result.exit_code == 0 else "failure"


class ExecutionService:
    def __init__(
        self,
        *,
        sandbox: Sandbox,
        repository: ExecutionRepository,
        limits_policy: LimitsPolicy,
        limiter: ConcurrencyLimiter,
        metrics: ExecutionMetrics | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._repository = repository
        self._limits_policy = limits_policy
        self._limiter = limiter
        self._metrics = metrics or NullMetrics()

    async def execute(self, request: ExecutionRequest) -> Execution:
        if request.client_request_id is not None:
            existing = await self._repository.get_by_client_request_id(request.client_request_id)
            if existing is not None:
                return existing

        limits = self._limits_policy.resolve(request.overrides)
        spec = SandboxSpec(
            language=request.language, code=request.code, stdin=request.stdin, limits=limits
        )
        async with self._limiter.slot():
            result = await self._sandbox.run(spec)

        execution = Execution(
            id=uuid.uuid4(),
            language=request.language,
            client_request_id=request.client_request_id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            timed_out=result.timed_out,
            oom_killed=result.oom_killed,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            created_at=datetime.now(UTC),
        )
        stored = await self._repository.save(execution)
        self._metrics.record(request.language.value, _outcome(result), result.duration_ms)
        return stored
