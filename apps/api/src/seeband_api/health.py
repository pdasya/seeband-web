"""Liveness check."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from seeband_core import __version__ as CORE_VERSION

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
