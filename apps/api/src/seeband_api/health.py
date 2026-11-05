"""Liveness check."""

from typing import Literal

from pydantic import BaseModel

from seeband_api.routing import api_router
from seeband_api.version import API_VERSION

router = api_router("health")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION)
