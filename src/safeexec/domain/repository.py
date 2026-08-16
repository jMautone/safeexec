"""Persistence port for executions and idempotency lookups."""

from typing import Protocol

from safeexec.models import Execution


class ExecutionRepository(Protocol):
    async def get_by_client_request_id(self, client_request_id: str) -> Execution | None: ...

    async def save(self, execution: Execution) -> Execution:
        """Persist and return the stored execution.

        If another execution already holds the same client_request_id,
        implementations must return that existing one instead.
        """
        ...
