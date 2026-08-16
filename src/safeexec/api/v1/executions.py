"""Thin /v1 router: validate at the edge, delegate to the domain."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from safeexec.domain.service import ExecutionService
from safeexec.models import ExecutionOut, ExecutionRequestIn

router = APIRouter(prefix="/v1")


def get_execution_service(request: Request) -> ExecutionService:
    service: ExecutionService = request.app.state.execution_service
    return service


@router.post("/executions", response_model=ExecutionOut)
async def create_execution(
    payload: ExecutionRequestIn,
    service: Annotated[ExecutionService, Depends(get_execution_service)],
) -> ExecutionOut:
    execution = await service.execute(payload.to_domain())
    return ExecutionOut.from_domain(execution)
