"""`POST /api/fit`: fit a model to measurements, in a process of its own, as a stream of events.

A request that cannot run is refused with a plain error, before the stream starts. Closing the
connection is how a client stops a fit, so a fit needs no id, and the API keeps no state.
"""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated, Any, Literal, Self

import numpy as np
from fastapi import Depends, Request
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core import __version__ as CORE_VERSION
from seeband_core.interpolation import in_fit_range
from seeband_core.model_interface import (
    Bounds,
    FitMode,
    FitRequest,
    FitResult,
    FitStatus,
    IterationUpdate,
    Quantity,
)

from seeband_api.errors import (
    INTERNAL_ERROR_CODE,
    ApiError,
    ErrorDetail,
    ErrorResponse,
)
from seeband_api.fit_runner import (
    FIT_FAILED_MESSAGE,
    FIT_PROCESS_DIED_MESSAGE,
    FIT_TIMEOUT_MESSAGE,
    FitRunnerDep,
)
from seeband_api.fit_worker import run_fit
from seeband_api.request_checks import (
    FiniteFloat,
    MaxPointsDep,
    MeasurementInput,
    PositiveFloat,
    check_degeneracy,
    check_parameter_names,
    check_point_counts,
    check_scattering,
    find_mode,
    invalid,
    to_measurements,
)
from seeband_api.request_limits import client_key
from seeband_api.request_logging import log_unhandled_exception
from seeband_api.routing import api_router, too_many_requests

router = api_router("fit")


class BoundsInput(BaseModel):
    lower: FiniteFloat
    upper: FiniteFloat

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.lower >= self.upper:
            raise ValueError("lower must be below upper")
        return self


class FitApiRequest(BaseModel):
    """What to fit.

    `start` holds every parameter of the mode in core units, including those of other scattering
    types. `bounds` overrides the description's bounds for fitted parameters, in core units.
    `measurements` holds each quantity of the mode, and only points from `min_temperature_k` to
    `max_temperature_k`, inclusive, enter the fit. `extrapolated` says that interpolation made up
    some of these points, so that the result says so too.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "model": "dpb",
                    "fit_mode": "dpb_s",
                    "start": {"m_eff": 1.01, "band_gap": 1000.0, "fermi_energy": -100.0},
                    "bounds": {"band_gap": {"lower": 0.0, "upper": 4000.0}},
                    "min_temperature_k": 100.0,
                    "max_temperature_k": 500.0,
                    "measurements": {
                        "seebeck": {
                            "temperature_k": [100.0, 200.0, 300.0, 400.0, 500.0],
                            "values": [2.0e-4, 2.3e-4, 8.9e-5, 3.8e-5, 2.1e-5],
                        }
                    },
                }
            ]
        }
    )

    model: str
    fit_mode: str
    scattering: str | None = None
    start: dict[str, FiniteFloat]
    bounds: dict[str, BoundsInput] = Field(default_factory=dict)
    min_temperature_k: PositiveFloat
    max_temperature_k: PositiveFloat
    band_1_degeneracy: PositiveFloat = 1.0
    band_2_degeneracy: PositiveFloat = 1.0
    extrapolated: Annotated[bool, Field(strict=True)] = False
    measurements: dict[Quantity, MeasurementInput]

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        if self.min_temperature_k >= self.max_temperature_k:
            raise ValueError("min_temperature_k must be below max_temperature_k")
        return self


class FitResponse(BaseModel):
    """The outcome of a fit, in core units.

    `converged` means that the fit ended normally, not that the result is sound. `iteration_limit`
    is not a converged result. `failed` returns the start values, with fixed text in `message`.
    `iterations` is left out for a single-pass mode. A value that is not finite is null.

    `parameter_errors` holds standard errors from the last solver run of each stage, holding other
    stages fixed, so in a staged fit they can be far too small, and are not plain uncertainties.
    `at_bounds` names fitted parameters that ended at a bound, which may be what set them.
    `known_issues` names known errors that apply, as in `GET /api/models`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "parameters": {"m_eff": 0.57, "band_gap": 910.0, "fermi_energy": -35.0},
                    "core_version": CORE_VERSION,
                    "status": "converged",
                    "parameter_errors": {"m_eff": 0.02, "band_gap": 12.0, "fermi_energy": 4.0},
                    "at_bounds": [],
                    "known_issues": [],
                }
            ]
        }
    )

    parameters: dict[str, float | None]
    core_version: str = Field(
        default=CORE_VERSION, description="Core software version for provenance, not certification."
    )
    status: FitStatus
    iterations: int | None = None
    message: str | None = None
    parameter_errors: dict[str, float]
    at_bounds: list[str]
    known_issues: list[str]


class FitStarted(BaseModel):
    """The fit has left the queue, and its process is starting."""

    type: Literal["started"] = "started"


class FitIteration(BaseModel):
    """Progress of an iterative fit, in core units. A single-pass mode sends none.

    `parameters` holds every parameter of the mode, in the form of a final result. One fitted after
    the loop, such as m1, keeps its start value here. A value that is not finite is null.
    """

    type: Literal["iteration"] = "iteration"
    iteration: int
    parameters: dict[str, float | None]


class FitDone(BaseModel):
    """The last event of a fit that ended, whatever its `status`."""

    type: Literal["done"] = "done"
    result: FitResponse


class FitError(BaseModel):
    """The last event of a fit with no result: `fit_timeout`, `fit_process_died` or `fit_failed`."""

    type: Literal["error"] = "error"
    error: ErrorResponse


FitEvent = Annotated[FitStarted | FitIteration | FitDone | FitError, Field(discriminator="type")]


def _stream_example(*events: BaseModel) -> str:
    return "".join(f"data: {event.model_dump_json(exclude_none=True)}\n\n" for event in events)


def _failure_example(code: str, message: str) -> dict[str, Any]:
    error = ErrorResponse(code=code, message=message, details=[])
    return {"value": _stream_example(FitStarted(), FitError(error=error))}


_EXAMPLE_RESULT = FitResponse(
    parameters={"m_eff": 0.57, "band_gap": 910.0, "fermi_energy": -35.0},
    status="converged",
    parameter_errors={"m_eff": 0.02, "band_gap": 12.0, "fermi_energy": 4.0},
    at_bounds=[],
    known_issues=[],
)
# The mock serves these as they stand, all at once.
_STREAM_EXAMPLES: dict[str, dict[str, Any]] = {
    "single_pass": {
        "value": _stream_example(FitStarted(), FitDone(result=_EXAMPLE_RESULT)),
    },
    "iterative": {
        "value": _stream_example(
            FitStarted(),
            FitIteration(
                iteration=1,
                parameters={"m_eff": 0.8, "band_gap": 950.0, "fermi_energy": -60.0},
            ),
            FitIteration(
                iteration=2,
                parameters={"m_eff": 0.6, "band_gap": 915.0, "fermi_energy": -38.0},
            ),
            FitDone(result=_EXAMPLE_RESULT.model_copy(update={"iterations": 2})),
        ),
    },
    "fit_timeout": _failure_example("fit_timeout", FIT_TIMEOUT_MESSAGE),
    "fit_process_died": _failure_example("fit_process_died", FIT_PROCESS_DIED_MESSAGE),
    "fit_failed": _failure_example("fit_failed", FIT_FAILED_MESSAGE),
}


def _refuse(details: list[ErrorDetail]) -> ApiError:
    return ApiError(HTTPStatus.UNPROCESSABLE_CONTENT, "invalid_fit", "Invalid fit", details)


def _check_bounds(body: FitApiRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    specs = {spec.name: spec for spec in fit_mode.parameters}
    in_scattering = {
        spec.name
        for spec in fit_mode.parameters_for(body.scattering if fit_mode.scattering else None)
    }
    details = []
    for name in body.bounds:
        spec = specs.get(name)
        if spec is None or spec.fit_bounds is None or name not in in_scattering:
            details.append(
                invalid("parameter_not_fitted", "This fit does not fit it", ["bounds", name])
            )
        elif not spec.bounds_editable:
            details.append(
                invalid("bounds_not_editable", "These bounds are fixed", ["bounds", name])
            )
    return details


def _check_measurements(body: FitApiRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    details = [
        invalid("missing_measurement", "This mode needs it", ["measurements", quantity])
        for quantity in fit_mode.quantities
        if quantity not in body.measurements
    ]
    details += [
        invalid("quantity_not_in_mode", "This mode does not use it", ["measurements", quantity])
        for quantity in body.measurements
        if quantity not in fit_mode.quantities
    ]
    return details


def _finite(parameters: Mapping[str, float]) -> dict[str, float | None]:
    return {
        name: float(value) if np.isfinite(value) else None for name, value in parameters.items()
    }


def _to_response(result: FitResult) -> FitResponse:
    return FitResponse(
        parameters=_finite(result.parameters),
        status=result.status,
        iterations=result.iterations,
        message=result.message,
        parameter_errors=dict(result.parameter_errors),
        at_bounds=list(result.at_bounds),
        known_issues=list(result.known_issues),
    )


def _to_core_request(body: FitApiRequest, max_points: int) -> tuple[str, FitRequest]:
    description, fit_mode = find_mode(body.model, body.fit_mode, "invalid_fit", "Invalid fit")
    scattering_details = check_scattering(body.scattering, fit_mode)
    details = [
        *scattering_details,
        *check_degeneracy(body.band_1_degeneracy, body.band_2_degeneracy, fit_mode),
        *check_parameter_names(list(body.start), "start", fit_mode),
        *_check_measurements(body, fit_mode),
        *check_point_counts(body.measurements, max_points),
    ]
    # The bounds depend on the scattering type, so this needs a valid one.
    if not scattering_details:
        details += _check_bounds(body, fit_mode)
    if details:
        raise _refuse(details)

    measurements = {}
    for quantity, measurement in to_measurements(body.measurements).items():
        inside = in_fit_range(measurement, body.min_temperature_k, body.max_temperature_k)
        if inside.temperature_k.size == 0:
            raise _refuse(
                [
                    invalid(
                        "no_points_in_range",
                        "The fit range holds none of these points",
                        ["measurements", quantity],
                    )
                ]
            )
        measurements[quantity] = inside

    return description.id, FitRequest(
        fit_mode=fit_mode.id,
        measurements=measurements,
        start=body.start,
        bounds={name: Bounds(b.lower, b.upper) for name, b in body.bounds.items()},
        scattering=body.scattering,
        band_1_degeneracy=body.band_1_degeneracy,
        band_2_degeneracy=body.band_2_degeneracy,
        extrapolated=body.extrapolated,
    )


class _FitEventStream(EventSourceResponse):
    """Keeps errors as JSON in the contract, as they are, with the 200 still as a stream.

    FastAPI writes the 200 as `text/event-stream` itself, and lists every other response of a route
    under this media type.
    """

    media_type = "application/json"


@dataclass(eq=False)
class _AcceptedFit:
    task: asyncio.Task[FitResult]
    events: asyncio.Queue[FitEvent | None]


async def _accept_fit(
    body: FitApiRequest, request: Request, runner: FitRunnerDep, max_points: MaxPointsDep
) -> AsyncIterator[_AcceptedFit]:
    """Refuses a request or takes its place in the queue, before the response starts.

    The fit belongs to the request rather than to the stream, whose generator a disconnect can stop
    before its first step. So the fit always ends here, however the request ends. If this is itself
    cancelled, at a stop of the server, the task still ends its process.
    """
    model_id, core_request = _to_core_request(body, max_points)
    events: asyncio.Queue[FitEvent | None] = asyncio.Queue()

    def on_iteration(update: IterationUpdate) -> None:
        events.put_nowait(
            FitIteration(iteration=update.iteration, parameters=_finite(update.parameters))
        )

    task = runner.submit(
        run_fit,
        model_id,
        core_request,
        client=client_key(request.scope),
        on_started=lambda: events.put_nowait(FitStarted()),
        on_iteration=on_iteration,
    )
    task.add_done_callback(lambda _: events.put_nowait(None))
    try:
        yield _AcceptedFit(task, events)
    finally:
        task.cancel()
        await asyncio.wait([task])


def _last_event(task: asyncio.Task[FitResult]) -> FitEvent:
    try:
        return FitDone(result=_to_response(task.result()))
    except ApiError as error:
        return FitError(
            error=ErrorResponse(code=error.code, message=error.message, details=error.details or [])
        )
    except Exception as error:
        # The response has started, so a client learns of this only from an event.
        log_unhandled_exception(error)
        return FitError(
            error=ErrorResponse(
                code=INTERNAL_ERROR_CODE, message="Internal server error", details=[]
            )
        )


@router.post(
    "/fit",
    response_class=_FitEventStream,
    response_model_exclude_none=True,
    responses={
        200: {
            "description": "Events of the fit. The last is `done` or `error`",
            "content": {"text/event-stream": {"examples": _STREAM_EXAMPLES}},
        },
        429: too_many_requests(("fit_queue_full", "client_fit_limit", "rate_limited")),
    },
)
async def post_fit(fit: Annotated[_AcceptedFit, Depends(_accept_fit)]) -> AsyncIterable[FitEvent]:
    while (event := await fit.events.get()) is not None:
        yield event
    yield _last_event(fit.task)
