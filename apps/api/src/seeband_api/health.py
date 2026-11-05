"""Liveness check."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from seeband_api.routing import api_router
from seeband_api.version import API_VERSION

router = api_router("health")


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "ok", "version": "1.0.0"}]}
    )

    status: Literal["ok"]
    version: str


@router.get("/health")
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION)
