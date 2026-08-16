"""Bounded concurrency for sandbox executions."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from safeexec.domain.errors import CapacityExceededError


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        if self._semaphore.locked():
            raise CapacityExceededError(
                "execution capacity exhausted; retry shortly or reduce request rate"
            )
        async with self._semaphore:
            yield
