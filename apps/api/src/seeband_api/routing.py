"""How routes join the API."""

from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter

from seeband_api.errors import ERROR_EXAMPLES, ErrorResponse

_ERROR_CONTENT = {
    "application/json": {
        "examples": {name: {"value": example} for name, example in ERROR_EXAMPLES.items()}
    }
}


def too_many_requests(examples: Iterable[str] = ("rate_limited",)) -> dict[str, Any]:
    """The 429 of a route with a rate limit, with the hint a client needs."""
    return {
        "model": ErrorResponse,
        "description": "Too many requests from this client, or for the server",
        "headers": {"Retry-After": {"schema": {"type": "integer"}, "example": 5}},
        "content": {
            "application/json": {
                "examples": {name: {"value": ERROR_EXAMPLES[name]} for name in examples}
            }
        },
    }


def api_router(tag: str) -> APIRouter:
    """Creates a router under `/api`, to be included directly in the app.

    Declaring the error format as the default response replaces FastAPI's own 422 schema, which the
    API does not send. Its named examples are what the mock serves.

    Include these routers in the app with no further prefix, and do not nest or mount them: FastAPI
    then records the route's path without the outer prefix, and the logs would show the wrong route.
    """
    return APIRouter(
        prefix="/api",
        tags=[tag],
        responses={"default": {"model": ErrorResponse, "content": _ERROR_CONTENT}},
    )
