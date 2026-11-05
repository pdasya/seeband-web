"""`POST /api/calc`: curves for given parameters, and optionally their RMSE. It keeps no state."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Annotated, Self

import numpy as np
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    CurveKind,
    CurveRequest,
    FitMode,
    Measurement,
    ModelDescription,
    Quantity,
)

from seeband_api.calc_pool import CalcPoolDep
from seeband_api.calc_worker import CalcOutcome, CalculationFailed, calculate
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.request_logging import log_calculation_failure
from seeband_api.routing import api_router

router = api_router("calc")

MAX_POINTS = 1000
# Live RMSE needs speed. A grid of 200 is about 3.6 times slower. On the demo dataset, 50 points
# changed an RMSE by about 0.3 % at default parameters, and up to about 4 % near a good fit, where
# the RMSE is small. Ask for 200 for a value to report.
DEFAULT_RMSE_POINTS = 50

# Strict, so that `true` or "1.5" are refused here as the contract and the mock refuse them.
FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
GridPoints = Annotated[int, Field(ge=2, le=MAX_POINTS, strict=True)]


class MeasurementInput(BaseModel):
    """Measured points, with values in V/K for S, ohm m for rho and m^3/C for R_H."""

    temperature_k: Annotated[list[PositiveFloat], Field(min_length=1)]
    values: Annotated[list[FiniteFloat], Field(min_length=1)]

    @model_validator(mode="after")
    def _same_length(self) -> Self:
        if len(self.temperature_k) != len(self.values):
            raise ValueError("temperature_k and values must have the same length")
        return self


class CalcRequest(BaseModel):
    """What to calculate.

    `parameters` holds every parameter of the mode in core units, including those of other
    scattering types. Values outside a control's range are allowed, as a fit can end there. `points`
    defaults to the model's. `measurements` gives an RMSE for each quantity, and should hold only
    points in the fit range. `extrapolated` says that interpolation made up some of these points.

    `kind` chooses the curves, and `GET /api/models` lists which a mode offers. `measurements` need
    the `measured` kind, because the known issues of a response are those of its curves, and an RMSE
    of other curves would not carry its own.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "model": "dpb",
                    "fit_mode": "dpb_s_rho",
                    "scattering": "acPh",
                    "parameters": {
                        "m_eff": 1.01,
                        "band_gap": 1000.0,
                        "fermi_energy": -100.0,
                        "A": 40000.0,
                        "B": 1.0,
                        "C": 1.0,
                        "D": 1.0,
                        "F": 1000.0,
                        "G": 1.0,
                    },
                    "min_temperature_k": 100.0,
                    "max_temperature_k": 500.0,
                    "points": 5,
                    "measurements": {
                        "seebeck": {
                            "temperature_k": [100.0, 300.0, 500.0],
                            "values": [2.0e-4, 9.0e-5, 2.0e-5],
                        }
                    },
                }
            ]
        }
    )

    model: str
    fit_mode: str
    scattering: str | None = None
    parameters: dict[str, FiniteFloat]
    min_temperature_k: PositiveFloat
    max_temperature_k: PositiveFloat
    kind: CurveKind = "measured"
    points: GridPoints | None = None
    band_1_degeneracy: PositiveFloat = 1.0
    band_2_degeneracy: PositiveFloat = 1.0
    extrapolated: Annotated[bool, Field(strict=True)] = False
    measurements: dict[Quantity, MeasurementInput] = Field(default_factory=dict)
    rmse_points: GridPoints = DEFAULT_RMSE_POINTS

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        if self.min_temperature_k >= self.max_temperature_k:
            raise ValueError("min_temperature_k must be below max_temperature_k")
        return self


class RmseResponse(BaseModel):
    """`value` is null where the result is not finite, as when the model has no finite value."""

    value: float | None
    unit: str


class CalcResponse(BaseModel):
    """Curves by name, where each name ends in its unit, and null marks a value that is not finite.

    `known_issues` names known errors that apply to this result, as in `GET /api/models`. `rmse` is
    empty without measurements.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "temperature_k": [100.0, 200.0, 300.0, 400.0, 500.0],
                    "curves": {
                        "seebeck_v_per_k": [2.0573e-4, 2.2818e-4, 8.8928e-5, 3.7589e-5, 2.0745e-5],
                        "resistivity_ohm_m": [
                            3.6627e-5,
                            8.4229e-5,
                            6.7638e-5,
                            4.9129e-5,
                            3.9895e-5,
                        ],
                    },
                    "known_issues": [],
                    "rmse": {"seebeck": {"value": 3.385, "unit": "uV/K"}},
                }
            ]
        }
    )

    temperature_k: list[float]
    curves: dict[str, list[float | None]]
    known_issues: list[str]
    rmse: dict[Quantity, RmseResponse]


def _invalid(code: str, message: str, location: list[str | int]) -> ErrorDetail:
    return ErrorDetail(location=["body", *location], code=code, message=message)


def _refuse(details: list[ErrorDetail]) -> ApiError:
    return ApiError(
        HTTPStatus.UNPROCESSABLE_CONTENT, "invalid_calculation", "Invalid calculation", details
    )


def _find_mode(body: CalcRequest) -> tuple[ModelDescription, FitMode]:
    descriptions = {description.id: description for description in registry.descriptions()}
    description = descriptions.get(body.model)
    if description is None:
        raise _refuse([_invalid("unknown_model", "This model does not exist", ["model"])])
    try:
        fit_mode = description.fit_mode(body.fit_mode)
    except KeyError:
        detail = _invalid("unknown_fit_mode", "This model has no such fit mode", ["fit_mode"])
        raise _refuse([detail]) from None
    if fit_mode.disabled:
        raise ApiError(
            HTTPStatus.CONFLICT,
            "fit_mode_disabled",
            "This fit mode is disabled until its known issue is fixed",
            [
                _invalid(issue.id, "A known issue disables this mode", ["fit_mode"])
                for issue in fit_mode.known_issues
                if issue.severity == "disabled"
            ],
        )
    return description, fit_mode


def _check_scattering(body: CalcRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    if body.scattering is None:
        if fit_mode.scattering:
            return [_invalid("missing_scattering", "This mode needs one", ["scattering"])]
    elif body.scattering not in fit_mode.scattering:
        return [_invalid("unknown_scattering", "This mode has no such type", ["scattering"])]
    return []


def _check_degeneracy(body: CalcRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    if fit_mode.degeneracy is not None:
        return []
    return [
        _invalid("degeneracy_not_in_mode", "This mode has no band degeneracy", [field])
        for field, value in (
            ("band_1_degeneracy", body.band_1_degeneracy),
            ("band_2_degeneracy", body.band_2_degeneracy),
        )
        if value != 1
    ]


def _check_parameters(body: CalcRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    expected = {spec.name for spec in fit_mode.parameters}
    missing = [
        _invalid("missing_parameter", "This mode needs it", ["parameters", spec.name])
        for spec in fit_mode.parameters
        if spec.name not in body.parameters
    ]
    unknown = [
        _invalid("unknown_parameter", "This mode has no such parameter", ["parameters", name])
        for name in body.parameters
        if name not in expected
    ]
    return missing + unknown


def _check_measurements(body: CalcRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    details = []
    for quantity, measurement in body.measurements.items():
        if quantity not in fit_mode.quantities:
            details.append(
                _invalid(
                    "quantity_not_in_mode",
                    "This mode has no such curve",
                    ["measurements", quantity],
                )
            )
        elif quantity != "seebeck" and 0 in measurement.values:
            # The RMSE of rho and R_H is a percent of the data, which has no meaning at 0.
            index = measurement.values.index(0)
            details.append(
                _invalid(
                    "zero_measured_value",
                    "A relative RMSE needs values other than 0",
                    ["measurements", quantity, "values", index],
                )
            )
    return details


def _finite_or_none(values: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in values]


def _to_response(outcome: CalcOutcome) -> CalcResponse:
    return CalcResponse(
        temperature_k=_finite_or_none(outcome.curve.temperature_k),  # type: ignore[arg-type]
        curves={name: _finite_or_none(values) for name, values in outcome.curve.curves.items()},
        known_issues=list(outcome.curve.known_issues),
        rmse={
            quantity: RmseResponse(value=rmse.value, unit=rmse.unit)
            for quantity, rmse in outcome.rmse.items()
        },
    )


def _measurements(body: CalcRequest) -> Mapping[Quantity, Measurement]:
    return {
        quantity: Measurement(np.array(measurement.temperature_k), np.array(measurement.values))
        for quantity, measurement in body.measurements.items()
    }


@router.post("/calc")
async def post_calc(body: CalcRequest, pool: CalcPoolDep) -> CalcResponse:
    description, fit_mode = _find_mode(body)
    details = [
        *_check_scattering(body, fit_mode),
        *_check_degeneracy(body, fit_mode),
        *_check_parameters(body, fit_mode),
        *_check_measurements(body, fit_mode),
    ]
    if details:
        raise _refuse(details)
    if body.measurements and body.kind != "measured":
        detail = _invalid(
            "measurements_need_measured_kind", "RMSE compares the measured curves", ["kind"]
        )
        raise _refuse([detail])
    reason = fit_mode.unavailable_reason(body.kind)
    if reason is not None:
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "curve_unavailable",
            "This fit mode does not offer this curve",
            [_invalid(reason, "See curve_unavailable in the API's README", ["kind"])],
        )

    request = CurveRequest(
        fit_mode=fit_mode.id,
        parameters=body.parameters,
        min_temperature_k=body.min_temperature_k,
        max_temperature_k=body.max_temperature_k,
        points=body.points or description.default_curve_points,
        scattering=body.scattering,
        kind=body.kind,
        band_1_degeneracy=body.band_1_degeneracy,
        band_2_degeneracy=body.band_2_degeneracy,
        extrapolated=body.extrapolated,
    )
    try:
        outcome = await pool.run(
            calculate, description.id, request, _measurements(body), body.rmse_points
        )
    except CalculationFailed as error:
        log_calculation_failure(str(error))
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "calculation_failed",
            "The calculation has no result for these parameters and temperatures",
        ) from None
    # A long list takes a moment to convert, so this leaves the event loop free too.
    return await run_in_threadpool(_to_response, outcome)
