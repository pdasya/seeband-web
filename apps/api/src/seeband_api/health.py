"""Liveness and readiness checks."""

from typing import Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from seeband_core import __version__ as CORE_VERSION

from seeband_api.calc_pool import CalcPool
from seeband_api.errors import ApiError
from seeband_api.routing import api_router
from seeband_api.version import API_COMMIT, API_VERSION

router = api_router("health")


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"status": "ok", "version": "1.0.0", "core_version": CORE_VERSION}]
        }
    )

    status: Literal["ok"]
    version: str
    commit: str | None = Field(
        default=None,
        description=(
            "The commit the API was built from, with -dirty for uncommitted changes, or null if "
            "unknown. For provenance."
        ),
    )
    core_version: str = Field(
        default=CORE_VERSION, description="Core software version for provenance, not certification."
    )


@router.get("/health")
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION, commit=API_COMMIT)


class ReadyResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ready"}]})

    status: Literal["ready"]


@router.get(
    "/ready",
    responses={503: {"description": "The calculation workers are not ready yet."}},
)
async def get_ready(request: Request) -> ReadyResponse:
    """Whether the API can calculate: its worker processes have started and answered.

    `/api/health` says the server answers; this says it can also take calculations, so that a proxy
    or an orchestrator sends traffic only once it can.
    """
    pool: CalcPool = request.app.state.calc_pool
    if not pool.ready:
        raise ApiError(
            503,
            "not_ready",
            "The calculation workers are starting. Try again shortly.",
            headers={"Retry-After": "1"},
        )
    return ReadyResponse(status="ready")
