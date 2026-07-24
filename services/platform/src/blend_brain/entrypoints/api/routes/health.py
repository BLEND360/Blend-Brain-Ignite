"""Orchestrator-facing liveness and readiness endpoints."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Literal, cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from blend_brain.shared.application.configuration import ServiceSettings

router = APIRouter(prefix="/health", tags=["system"])


class HealthResponse(BaseModel):
    """Operational health response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "not_ready"]
    service: str
    version: str


@router.get("/live", response_model=HealthResponse, operation_id="getLiveness")
async def get_liveness(request: Request) -> HealthResponse:
    """Confirm that the API process can serve requests."""
    settings = cast("ServiceSettings", request.app.state.settings)
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    operation_id="getReadiness",
)
async def get_readiness(request: Request) -> HealthResponse | JSONResponse:
    """Confirm that application startup completed and traffic is safe."""
    settings = cast("ServiceSettings", request.app.state.settings)
    response = HealthResponse(
        status="ok" if request.app.state.ready else "not_ready",
        service=settings.app_name,
        version=settings.app_version,
    )
    if request.app.state.ready:
        return response
    return JSONResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE, content=response.model_dump())
