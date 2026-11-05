"""How routes join the API."""

from fastapi import APIRouter

from seeband_api.errors import ErrorResponse


def api_router(tag: str) -> APIRouter:
    """Creates a router under `/api`, to be included directly in the app.

    Declaring the error format as the default response replaces FastAPI's own 422 schema, which the
    API does not send. Include these routers in the app with no further prefix, and do not nest or
    mount them: FastAPI then records the route's path without the outer prefix, and the logs would
    show the wrong route.
    """
    return APIRouter(prefix="/api", tags=[tag], responses={"default": {"model": ErrorResponse}})
