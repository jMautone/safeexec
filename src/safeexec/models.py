"""Edge schemas (pydantic) and domain entities shared across layers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MAX_CODE_CHARS = 65_536
MAX_STDIN_CHARS = 16_384


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    timeout_ms: int
    memory_mb: int
    cpus: float
    max_output_bytes: int


@dataclass(frozen=True, slots=True)
class LimitOverrides:
    timeout_ms: int | None = None
    memory_mb: int | None = None
    cpus: float | None = None
    max_output_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    language: Language
    code: str
    stdin: str | None = None
    overrides: LimitOverrides = LimitOverrides()
    client_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class Execution:
    id: uuid.UUID
    language: Language
    client_request_id: str | None
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int
    timed_out: bool
    oom_killed: bool
    stdout_truncated: bool
    stderr_truncated: bool
    created_at: datetime


class LimitsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: int | None = Field(default=None, gt=0)
    memory_mb: int | None = Field(default=None, gt=0)
    cpus: float | None = Field(default=None, gt=0)
    max_output_bytes: int | None = Field(default=None, gt=0)


class ExecutionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language
    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)
    stdin: str | None = Field(default=None, max_length=MAX_STDIN_CHARS)
    limits: LimitsIn | None = None
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)

    def to_domain(self) -> ExecutionRequest:
        limits = self.limits or LimitsIn()
        return ExecutionRequest(
            language=self.language,
            code=self.code,
            stdin=self.stdin,
            overrides=LimitOverrides(
                timeout_ms=limits.timeout_ms,
                memory_mb=limits.memory_mb,
                cpus=limits.cpus,
                max_output_bytes=limits.max_output_bytes,
            ),
            client_request_id=self.client_request_id,
        )


class ExecutionOut(BaseModel):
    id: uuid.UUID
    language: Language
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int
    timed_out: bool
    oom_killed: bool
    stdout_truncated: bool
    stderr_truncated: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, execution: Execution) -> ExecutionOut:
        return cls(
            id=execution.id,
            language=execution.language,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            timed_out=execution.timed_out,
            oom_killed=execution.oom_killed,
            stdout_truncated=execution.stdout_truncated,
            stderr_truncated=execution.stderr_truncated,
            created_at=execution.created_at,
        )
