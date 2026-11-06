"""Logging limited to what the data handling policy allows.

Each request produces one line with its method, route template, status and duration. Requests can
carry unpublished measurements, so this module logs nothing from their bodies, query strings or
raw paths, and no exception messages, because a message can quote its input. An unhandled
exception is logged by type and code location only.

An `Exception` stops here on purpose. Letting it continue would make the server log its full
traceback, message included. Cancellation and other `BaseException`s must continue, so the server
can still print those: see the limits in the README.
"""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, override

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from seeband_api.errors import internal_error_response

UNMATCHED_ROUTE = "<unmatched>"
OTHER_METHOD = "OTHER"

# A client can send any token as a method, so one could carry data.
_KNOWN_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)

_logger = logging.getLogger("seeband_api")


class _JsonLineFormatter(logging.Formatter):
    """Writes fixed fields only. Tracebacks attached to a record are dropped."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = getattr(record, "fields", {})
        return json.dumps(
            {
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                **fields,
            }
        )


def _drop_record(_: logging.LogRecord) -> bool:
    return False


def configure_logging(level: str) -> None:
    """Sets up the API's logger and silences the server's access log, which logs query strings.

    This uses a filter because uvicorn's own logging setup clears a logger's `disabled` flag, and
    that setup can run after this function.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonLineFormatter())
    _logger.handlers = [handler]
    _logger.setLevel(level)
    _logger.propagate = False
    logging.getLogger("uvicorn.access").addFilter(_drop_record)


def log_calculation_failure(exception_type: str) -> None:
    """Records a failure in a calculation or fit, as it could also be a bug in the core."""
    _logger.warning("calculation_failed", extra={"fields": {"exception_type": exception_type}})


def log_unhandled_exception(error: Exception) -> None:
    frames = [
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(error.__traceback__)
    ]
    _logger.error(
        "unhandled_exception",
        extra={"fields": {"exception_type": type(error).__name__, "frames": frames}},
    )


class RequestLoggingMiddleware:
    """Logs each request and turns an unhandled exception into the API's 500 response.

    A plain ASGI middleware, because `BaseHTTPMiddleware` interferes with streaming responses.
    """

    def __init__(self, app: ASGIApp, unparameterised_paths: frozenset[str]) -> None:
        self._app = app
        # Routes that FastAPI adds itself, such as the docs, do not record a route template.
        self._unparameterised_paths = unparameterised_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope["method"]
        started_s = perf_counter()
        status_code: int | None = None

        async def send_and_record_status(message: Message) -> None:
            nonlocal status_code
            await send(message)
            if message["type"] == "http.response.start":
                status_code = message["status"]

        try:
            try:
                await self._app(scope, receive, send_and_record_status)
            except Exception as error:
                log_unhandled_exception(error)
            else:
                return
            # This runs outside the `except` block, so that a failure here does not carry the
            # original exception, with its message, as its context. If the response has started,
            # returning makes the server close the connection.
            if status_code is None:
                await internal_error_response()(scope, receive, send_and_record_status)
        finally:
            # The status stays None if the task is cancelled before the response starts.
            _logger.info(
                "request",
                extra={
                    "fields": {
                        "method": method if method in _KNOWN_METHODS else OTHER_METHOD,
                        "route": self._route_template(scope),
                        "status": status_code,
                        "duration_ms": round((perf_counter() - started_s) * 1e3, 1),
                    }
                },
            )

    def _route_template(self, scope: Scope) -> str:
        template = getattr(scope.get("route"), "path", None)
        if isinstance(template, str):
            return template
        path = scope["path"]
        return path if path in self._unparameterised_paths else UNMATCHED_ROUTE
