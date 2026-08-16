"""Application factory and dependency wiring."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from safeexec import __version__
from safeexec.adapters.container_sandbox import ContainerSandbox, ContainerSandboxConfig
from safeexec.adapters.metrics import get_metrics
from safeexec.adapters.postgres_repository import PostgresExecutionRepository
from safeexec.api.health import router as health_router
from safeexec.api.metrics import router as metrics_router
from safeexec.api.middleware import RequestContextMiddleware
from safeexec.api.v1.executions import router as v1_router
from safeexec.config import Settings, get_settings
from safeexec.domain.concurrency import ConcurrencyLimiter
from safeexec.domain.errors import (
    CapacityExceededError,
    LimitsOutOfRangeError,
    SandboxUnavailableError,
)
from safeexec.domain.limits import LimitsPolicy
from safeexec.domain.service import ExecutionService
from safeexec.logging import configure_logging
from safeexec.models import Language, ResourceLimits

logger = logging.getLogger(__name__)


def limits_policy_from_settings(settings: Settings) -> LimitsPolicy:
    return LimitsPolicy(
        defaults=ResourceLimits(
            timeout_ms=settings.default_timeout_ms,
            memory_mb=settings.default_memory_mb,
            cpus=settings.default_cpus,
            max_output_bytes=settings.default_max_output_bytes,
        ),
        maximums=ResourceLimits(
            timeout_ms=settings.max_timeout_ms,
            memory_mb=settings.max_memory_mb,
            cpus=settings.max_cpus,
            max_output_bytes=settings.max_max_output_bytes,
        ),
    )


def container_sandbox_from_settings(settings: Settings) -> ContainerSandbox:
    return ContainerSandbox(
        ContainerSandboxConfig(
            images={
                Language.PYTHON: settings.python_image,
                Language.JAVASCRIPT: settings.node_image,
            },
            user=settings.sandbox_user,
            runtime=settings.sandbox_runtime,
            daemon_timeout_seconds=settings.docker_timeout_seconds,
            workdir_base=settings.sandbox_workdir_base,
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.execution_service = ExecutionService(
        sandbox=container_sandbox_from_settings(settings),
        repository=PostgresExecutionRepository(session_factory),
        limits_policy=limits_policy_from_settings(settings),
        limiter=ConcurrencyLimiter(settings.max_concurrent_executions),
        metrics=get_metrics(),
    )
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="SafeExec", version=__version__, lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(v1_router)

    @app.exception_handler(LimitsOutOfRangeError)
    async def limits_out_of_range(request: Request, exc: LimitsOutOfRangeError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(CapacityExceededError)
    async def capacity_exceeded(request: Request, exc: CapacityExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=429, content={"detail": str(exc)}, headers={"Retry-After": "1"}
        )

    @app.exception_handler(SandboxUnavailableError)
    async def sandbox_unavailable(request: Request, exc: SandboxUnavailableError) -> JSONResponse:
        logger.error("sandbox backend unavailable", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "execution backend temporarily unavailable; retry later"},
        )

    return app


app = create_app()
