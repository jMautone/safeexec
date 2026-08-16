from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from safeexec.api.v1.executions import get_execution_service
from safeexec.domain.service import ExecutionService
from safeexec.main import create_app


@pytest.fixture
def app(service: ExecutionService) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_execution_service] = lambda: service
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
