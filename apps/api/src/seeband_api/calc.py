"""`POST /api/calc`: curves for given parameters, and optionally their RMSE. It keeps no state."""

from http import HTTPStatus
from typing import Annotated, Self

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core.model_interface import (
    CurveKind,
    CurveRequest,
    FitMode,
    Quantity,
)

from seeband_api.calc_pool import CalcPoolDep
from seeband_api.calc_worker import CalcOutcome, CalculationFailed, calculate
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.json_values import finite_or_none
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
from seeband_api.request_logging import log_calculation_failure
from seeband_api.routing import api_router

router = api_router("calc")

MAX_POINTS = 1000
# Live RMSE needs speed. A grid of 200 is about 3.6 times slower. On the demo dataset, 50 points
# changed an RMSE by about 0.3 % at default parameters, and up to about 4 % near a good fit, where
# the RMSE is small. Ask for 200 for a value to report.
DEFAULT_RMSE_POINTS = 50

GridPoints = Annotated[int, Field(ge=2, le=MAX_POINTS, strict=True)]


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


def _refuse(details: list[ErrorDetail]) -> ApiError:
    return ApiError(
        HTTPStatus.UNPROCESSABLE_CONTENT, "invalid_calculation", "Invalid calculation", details
    )


def _check_measurements(body: CalcRequest, fit_mode: FitMode) -> list[ErrorDetail]:
    details = []
    for quantity, measurement in body.measurements.items():
        if quantity not in fit_mode.quantities:
            details.append(
                invalid(
                    "quantity_not_in_mode",
                    "This mode has no such curve",
                    ["measurements", quantity],
                )
            )
        elif quantity != "seebeck" and 0 in measurement.values:
            # The RMSE of rho and R_H is a percent of the data, which has no meaning at 0.
            index = measurement.values.index(0)
            details.append(
                invalid(
                    "zero_measured_value",
                    "A relative RMSE needs values other than 0",
                    ["measurements", quantity, "values", index],
                )
            )
    return details


def _to_response(outcome: CalcOutcome) -> CalcResponse:
    return CalcResponse(
        temperature_k=finite_or_none(outcome.curve.temperature_k),  # type: ignore[arg-type]
        curves={name: finite_or_none(values) for name, values in outcome.curve.curves.items()},
        known_issues=list(outcome.curve.known_issues),
        rmse={
            quantity: RmseResponse(value=rmse.value, unit=rmse.unit)
            for quantity, rmse in outcome.rmse.items()
        },
    )


@router.post("/calc")
async def post_calc(body: CalcRequest, pool: CalcPoolDep) -> CalcResponse:
    description, fit_mode = find_mode(
        body.model, body.fit_mode, "invalid_calculation", "Invalid calculation"
    )
    details = [
        *check_scattering(body.scattering, fit_mode),
        *check_degeneracy(body.band_1_degeneracy, body.band_2_degeneracy, fit_mode),
        *check_parameter_names(list(body.parameters), "parameters", fit_mode),
        *_check_measurements(body, fit_mode),
    ]
    if details:
        raise _refuse(details)
    if body.measurements and body.kind != "measured":
        detail = invalid(
            "measurements_need_measured_kind", "RMSE compares the measured curves", ["kind"]
        )
        raise _refuse([detail])
    reason = fit_mode.unavailable_reason(body.kind)
    if reason is not None:
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "curve_unavailable",
            "This fit mode does not offer this curve",
            [invalid(reason, "See curve_unavailable in the API's README", ["kind"])],
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
            calculate, description.id, request, to_measurements(body.measurements), body.rmse_points
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
