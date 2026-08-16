"""Postgres-backed execution repository with idempotency by client_request_id."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from safeexec.adapters.db import ExecutionRow, execution_from_row, row_from_execution
from safeexec.models import Execution


class PostgresExecutionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_client_request_id(self, client_request_id: str) -> Execution | None:
        async with self._session_factory() as session:
            row = await self._fetch(session, client_request_id)
            return execution_from_row(row) if row is not None else None

    async def save(self, execution: Execution) -> Execution:
        async with self._session_factory() as session:
            session.add(row_from_execution(execution))
            try:
                await session.commit()
            except IntegrityError:
                # Lost the race against a concurrent request with the same
                # client_request_id: the first stored result wins.
                await session.rollback()
                if execution.client_request_id is None:
                    raise
                existing = await self._fetch(session, execution.client_request_id)
                if existing is None:
                    raise
                return execution_from_row(existing)
            return execution

    @staticmethod
    async def _fetch(session: AsyncSession, client_request_id: str) -> ExecutionRow | None:
        result = await session.execute(
            select(ExecutionRow).where(ExecutionRow.client_request_id == client_request_id)
        )
        return result.scalar_one_or_none()
