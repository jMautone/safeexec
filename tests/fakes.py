"""Test doubles: domain is exercised without containers or a database."""

import asyncio
from dataclasses import dataclass, field

from safeexec.domain.sandbox import SandboxResult, SandboxSpec
from safeexec.models import Execution

SUCCESS_RESULT = SandboxResult(
    stdout="hello\n",
    stderr="",
    exit_code=0,
    duration_ms=12,
    timed_out=False,
    oom_killed=False,
    stdout_truncated=False,
    stderr_truncated=False,
)


@dataclass
class FakeSandbox:
    result: SandboxResult = SUCCESS_RESULT
    error: Exception | None = None
    release: asyncio.Event | None = None
    calls: list[SandboxSpec] = field(default_factory=list)

    async def run(self, spec: SandboxSpec) -> SandboxResult:
        self.calls.append(spec)
        if self.release is not None:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return self.result


class InMemoryExecutionRepository:
    def __init__(self) -> None:
        self.executions: list[Execution] = []

    async def get_by_client_request_id(self, client_request_id: str) -> Execution | None:
        for execution in self.executions:
            if execution.client_request_id == client_request_id:
                return execution
        return None

    async def save(self, execution: Execution) -> Execution:
        if execution.client_request_id is not None:
            existing = await self.get_by_client_request_id(execution.client_request_id)
            if existing is not None:
                return existing
        self.executions.append(execution)
        return execution
