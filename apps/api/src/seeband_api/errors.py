"""The one error format of the API, and the handlers that produce it.

The client translates errors by `code`. `message` is English text for developers. A validation
error leaves out Pydantic's copy of the submitted value. Its message or location can still quote
part of a request, such as a dictionary key, but only to the client that sent it.
"""

import json
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException

INTERNAL_ERROR_CODE = "internal_error"

_HTTP_ERROR_CODES: dict[int, str] = {
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
}


class ErrorDetail(BaseModel):
    """One problem in a request. `location` is the path to it, such as `["body", "points", 3]`."""

    location: list[str | int]
    code: str
    message: str


# More would only make an answer large: a request with an error in each of many values gets the
# first of them, and a count of the rest.
MAX_ERROR_DETAILS = 50


class ErrorResponse(BaseModel):
    """The body of every error response.

    `details` holds at most 50 problems, and `details_omitted` counts any more, left out.
    """

    code: str
    message: str
    details: list[ErrorDetail]
    details_omitted: int | None = None


def capped(code: str, message: str, details: list[ErrorDetail]) -> ErrorResponse:
    """An error with at most `MAX_ERROR_DETAILS` details, and the count of the rest."""
    omitted = len(details) - MAX_ERROR_DETAILS
    return ErrorResponse(
        code=code,
        message=message,
        details=details[:MAX_ERROR_DETAILS],
        details_omitted=omitted if omitted > 0 else None,
    )


ERROR_EXAMPLES: dict[str, dict[str, Any]] = {
    "internal_error": {
        "code": INTERNAL_ERROR_CODE,
        "message": "Internal server error",
        "details": [],
    },
    "not_found": {"code": "not_found", "message": "Not Found", "details": []},
    "calculation_failed": {
        "code": "calculation_failed",
        "message": "The calculation has no result for these parameters and temperatures",
        "details": [],
    },
    "calculation_timeout": {
        "code": "calculation_timeout",
        "message": "The calculation took too long",
        "details": [],
    },
    "calculation_unavailable": {
        "code": "calculation_unavailable",
        "message": "The calculation stopped unexpectedly. Try again.",
        "details": [],
    },
    "fit_mode_disabled": {
        "code": "fit_mode_disabled",
        "message": "This fit mode is disabled until its known issue is fixed",
        "details": [],
    },
    "invalid_fit": {
        "code": "invalid_fit",
        "message": "Invalid fit",
        "details": [
            {
                "location": ["body", "bounds", "m_eff"],
                "code": "parameter_not_fitted",
                "message": "This fit does not fit it",
            }
        ],
    },
    "fit_queue_full": {
        "code": "fit_queue_full",
        "message": "Too many fits are running. Try again shortly.",
        "details": [],
    },
    "rate_limited": {"code": "rate_limited", "message": "Too many requests", "details": []},
    "request_too_large": {
        "code": "request_too_large",
        "message": "A request can hold at most 10000000 bytes",
        "details": [],
    },
    "calculation_busy": {
        "code": "calculation_busy",
        "message": "Too many calculations are waiting. Try again shortly.",
        "details": [],
    },
    "client_calc_limit": {
        "code": "client_calc_limit",
        "message": "At most 4 calculations of one client at once",
        "details": [],
    },
    "server_busy": {
        "code": "server_busy",
        "message": "Too many requests at once. Try again shortly.",
        "details": [],
    },
    "request_timeout": {
        "code": "request_timeout",
        "message": "A request's body must arrive within 60.0 s, with no pause over 10.0 s",
        "details": [],
    },
    "client_fit_limit": {
        "code": "client_fit_limit",
        "message": "This client has too many fits running or waiting",
        "details": [],
    },
    "invalid_parse_request": {
        "code": "invalid_parse_request",
        "message": "Invalid request",
        "details": [
            {
                "location": ["body", "mapping"],
                "code": "unknown_column",
                "message": "The text has no such column",
            }
        ],
    },
    "invalid_guess": {
        "code": "invalid_guess",
        "message": "Invalid request",
        "details": [
            {
                "location": ["body", "model"],
                "code": "unknown_model",
                "message": "This model does not exist",
            }
        ],
    },
    "guess_unavailable": {
        "code": "guess_unavailable",
        "message": "This model has no neural net guess",
        "details": [
            {
                "location": ["body", "model"],
                "code": "no_neural_net",
                "message": "See has_initial_guess in GET /api/models",
            }
        ],
    },
    "invalid_calculation": {
        "code": "invalid_calculation",
        "message": "Invalid calculation",
        "details": [
            {
                "location": ["body", "parameters", "m_eff"],
                "code": "missing_parameter",
                "message": "This mode needs it",
            }
        ],
    },
    "validation_error": {
        "code": "validation_error",
        "message": "Invalid request",
        "details": [
            {
                "location": ["body", "seebeck_v_per_k", 3],
                "code": "float_parsing",
                "message": "Input should be a valid number, unable to parse string as a number",
            }
        ],
    },
}


CHEMICAL_POTENTIAL_ERROR_MESSAGES = {
    "chemical_potential_zero_mass": "Band mass must be nonzero.",
    "chemical_potential_spb_fermi_energy": (
        "Fermi energy must lie inside the band selected by the mass sign."
    ),
    "chemical_potential_dpb_fermi_energy": (
        "Fermi energy must be below the higher valence-band edge for two hole bands."
    ),
}

CALCULATION_ERROR_EXAMPLES = {
    name: ERROR_EXAMPLES[name] for name in ("invalid_calculation", "calculation_failed")
} | {
    "calculation_without_chemical_potential": ERROR_EXAMPLES["calculation_failed"]
    | {
        "details": [
            {
                "location": ["body", "parameters"],
                "code": "chemical_potential_zero_mass",
                "message": CHEMICAL_POTENTIAL_ERROR_MESSAGES["chemical_potential_zero_mass"],
            }
        ]
    }
}


class ApiError(Exception):
    """An error a route reports to the client."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    error: ErrorResponse,
    headers: dict[str, str] | None = None,
) -> Response:
    # Plain `json.dumps` escapes a lone surrogate from a client's text, which UTF-8 cannot encode.
    return Response(
        json.dumps(error.model_dump(mode="json", exclude_none=True)),
        status_code=status_code,
        headers=headers,
        media_type="application/json",
    )


def internal_error_response() -> Response:
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorResponse(code=INTERNAL_ERROR_CODE, message="Internal server error", details=[]),
    )


def _handle_api_error(_: Request, error: Exception) -> Response:
    assert isinstance(error, ApiError)
    return error_response(
        error.status_code,
        capped(error.code, error.message, error.details or []),
        headers=error.headers,
    )


def _handle_http_exception(_: Request, error: Exception) -> Response:
    assert isinstance(error, HTTPException)
    code = _HTTP_ERROR_CODES.get(error.status_code, "http_error")
    # FastAPI allows a detail that is not text, and the error format does not.
    message = error.detail if isinstance(error.detail, str) else "HTTP error"
    return error_response(
        error.status_code,
        ErrorResponse(code=code, message=message, details=[]),
        # A 405 must keep its Allow header.
        headers=dict(error.headers) if error.headers else None,
    )


def _handle_validation_error(_: Request, error: Exception) -> Response:
    assert isinstance(error, RequestValidationError)
    items = error.errors()
    details = [
        # Pydantic's `input` and `ctx` hold submitted values, so they are left out.
        ErrorDetail(location=list(item["loc"]), code=item["type"], message=item["msg"])
        for item in items[:MAX_ERROR_DETAILS]
    ]
    omitted = len(items) - len(details)
    return error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorResponse(
            code="validation_error",
            message="Invalid request",
            details=details,
            details_omitted=omitted if omitted > 0 else None,
        ),
    )


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
