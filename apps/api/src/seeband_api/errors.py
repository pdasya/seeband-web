"""The one error format of the API, and the handlers that produce it.

The client translates errors by `code`. `message` is English text for developers. A validation
error leaves out Pydantic's copy of the submitted value. Its message or location can still quote
part of a request, such as a dictionary key, but only to the client that sent it.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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


class ErrorResponse(BaseModel):
    """The body of every error response."""

    code: str
    message: str
    details: list[ErrorDetail] | None


class ApiError(Exception):
    """An error a route reports to the client."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(
    status_code: int,
    error: ErrorResponse,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(error.model_dump(mode="json"), status_code=status_code, headers=headers)


def internal_error_response() -> JSONResponse:
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorResponse(code=INTERNAL_ERROR_CODE, message="Internal server error", details=None),
    )


def _handle_api_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)
    return error_response(
        error.status_code,
        ErrorResponse(code=error.code, message=error.message, details=error.details),
    )


def _handle_http_exception(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)
    code = _HTTP_ERROR_CODES.get(error.status_code, "http_error")
    # FastAPI allows a detail that is not text, and the error format does not.
    message = error.detail if isinstance(error.detail, str) else "HTTP error"
    return error_response(
        error.status_code,
        ErrorResponse(code=code, message=message, details=None),
        # A 405 must keep its Allow header.
        headers=dict(error.headers) if error.headers else None,
    )


def _handle_validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    details = [
        # Pydantic's `input` and `ctx` hold submitted values, so they are left out.
        ErrorDetail(location=list(item["loc"]), code=item["type"], message=item["msg"])
        for item in error.errors()
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorResponse(code="validation_error", message="Invalid request", details=details),
    )


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
