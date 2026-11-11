from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from rag_service.features.health.schemas import LivenessResponse, ReadinessResponse
from rag_service.features.health.service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service(request: Request) -> HealthService:
    service: HealthService = request.app.state.health_service
    return service


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Process is up. Must never touch dependencies."""
    return LivenessResponse()


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}
)
async def ready(
    response: Response, service: Annotated[HealthService, Depends(get_health_service)]
) -> ReadinessResponse:
    """Dependencies reachable. 503 when any check fails so orchestrators stop routing traffic."""
    report = await service.readiness()
    if report.status != "ok":
        response.status_code = 503
    return report
