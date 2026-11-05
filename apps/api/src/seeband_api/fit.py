"""`POST /api/fit`: fit a model to measurements, in a process of its own.

This answers with the final result. Progress and stopping come with A9.
"""

from http import HTTPStatus
from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core.interpolation import in_fit_range
from seeband_core.model_interface import Bounds, FitMode, FitRequest, FitResult, FitStatus, Quantity

from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.fit_runner import FitRunnerDep
from seeband_api.fit_worker import run_fit
from seeband_api.request_checks import (
    FiniteFloat,
    MeasurementInput,
    PositiveFloat,
    check_degeneracy,
    check_parameter_names,
    check_scattering,
    find_mode,
    invalid,
    to_measurements,
)
from seeband_api.routing import api_router

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
                    "status": "converged",
                    "parameter_errors": {"m_eff": 0.02, "band_gap": 12.0, "fermi_energy": 4.0},
                    "at_bounds": [],
                    "known_issues": [],
                }
            ]
        }
    )

    parameters: dict[str, float | None]
    status: FitStatus
    iterations: int | None = None
    message: str | None = None
    parameter_errors: dict[str, float]
    at_bounds: list[str]
    known_issues: list[str]


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


def _to_response(result: FitResult) -> FitResponse:
    return FitResponse(
        parameters={
            name: float(value) if np.isfinite(value) else None
            for name, value in result.parameters.items()
        },
        status=result.status,
        iterations=result.iterations,
        message=result.message,
        parameter_errors=dict(result.parameter_errors),
        at_bounds=list(result.at_bounds),
        known_issues=list(result.known_issues),
    )


@router.post("/fit", response_model_exclude_none=True)
async def post_fit(body: FitApiRequest, runner: FitRunnerDep) -> FitResponse:
    description, fit_mode = find_mode(body.model, body.fit_mode, "invalid_fit")
    scattering_details = check_scattering(body.scattering, fit_mode)
    details = [
        *scattering_details,
        *check_degeneracy(body.band_1_degeneracy, body.band_2_degeneracy, fit_mode),
        *check_parameter_names(list(body.start), "start", fit_mode),
        *_check_measurements(body, fit_mode),
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

    request = FitRequest(
        fit_mode=fit_mode.id,
        measurements=measurements,
        start=body.start,
        bounds={name: Bounds(b.lower, b.upper) for name, b in body.bounds.items()},
        scattering=body.scattering,
        band_1_degeneracy=body.band_1_degeneracy,
        band_2_degeneracy=body.band_2_degeneracy,
        extrapolated=body.extrapolated,
    )
    return _to_response(await runner.run(run_fit, description.id, request))
