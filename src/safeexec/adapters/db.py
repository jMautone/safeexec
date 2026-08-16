"""SQLAlchemy table mapping for executions."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from safeexec.models import Execution, Language


class Base(DeclarativeBase):
    pass


class ExecutionRow(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    client_request_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    language: Mapped[str] = mapped_column(String(32))
    stdout: Mapped[str] = mapped_column(Text)
    stderr: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    timed_out: Mapped[bool] = mapped_column(Boolean)
    oom_killed: Mapped[bool] = mapped_column(Boolean)
    stdout_truncated: Mapped[bool] = mapped_column(Boolean)
    stderr_truncated: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def row_from_execution(execution: Execution) -> ExecutionRow:
    return ExecutionRow(
        id=execution.id,
        client_request_id=execution.client_request_id,
        language=execution.language.value,
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


def execution_from_row(row: ExecutionRow) -> Execution:
    return Execution(
        id=row.id,
        language=Language(row.language),
        client_request_id=row.client_request_id,
        stdout=row.stdout,
        stderr=row.stderr,
        exit_code=row.exit_code,
        duration_ms=row.duration_ms,
        timed_out=row.timed_out,
        oom_killed=row.oom_killed,
        stdout_truncated=row.stdout_truncated,
        stderr_truncated=row.stderr_truncated,
        created_at=row.created_at,
    )
