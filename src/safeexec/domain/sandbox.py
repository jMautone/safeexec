"""Sandbox contract: the executor is a detail behind this interface."""

from dataclasses import dataclass
from typing import Protocol

from safeexec.models import Language, ResourceLimits


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    language: Language
    code: str
    stdin: str | None
    limits: ResourceLimits


@dataclass(frozen=True, slots=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int
    timed_out: bool
    oom_killed: bool
    stdout_truncated: bool
    stderr_truncated: bool


class Sandbox(Protocol):
    async def run(self, spec: SandboxSpec) -> SandboxResult: ...
