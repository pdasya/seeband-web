"""`POST /api/guess`: DPB neural or SPB numerical Seebeck start values.

No net that fits the data is a normal answer, not an error, so that a client can say why and keep
its current values. It keeps no state, and the examples are hand-rounded so that the contract does
not depend on the machine: `tests/test_guess.py` compares them with real results.
"""

from http import HTTPStatus
from typing import Annotated, Any, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from seeband_core.model_catalog import registry
from seeband_core.neural_nets import NET_RANGES_K, NoNeuralNet

from seeband_api.calc_pool import CalcPoolDep
from seeband_api.calc_worker import CalculationFailed
from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.guess_worker import GuessOutcome, guess, numerical_guess
from seeband_api.request_checks import (
    FiniteFloat,
    MaxPointsDep,
    PositiveFloat,
    too_many_points,
)
from seeband_api.request_logging import log_calculation_failure
from seeband_api.routing import api_router, too_many_requests

router = api_router("guess")

GuessWarning = Literal[
    "unsorted_temperature",
    "underdetermined_fit",
    "m_eff_rounds_to_zero",
    "estimate_at_bound",
    "large_estimate_residual",
    "low_temperature_omitted",
]

_NET_RANGE_EXAMPLE = {"min_temperature_k": 400.0, "max_temperature_k": 700.0}
# Every third row of the example set 01_Fe2VAl09Si01, rounded to 4 digits.
REQUEST_EXAMPLE: dict[str, Any] = {
    "model": "dpb",
    "temperature_k": [25.0, 100.0, 175.0, 250.0, 325.0, 400.0, 475.0, 550.0, 625.0, 700.0],
    "seebeck_v_per_k": [
        -8.983e-6,
        -5.032e-5,
        -7.751e-5,
        -9.938e-5,
        -1.174e-4,
        -1.202e-4,
        -1.046e-4,
        -8.192e-5,
        -6.19e-5,
        -4.7e-5,
    ],
}
# `guess` is what REQUEST_EXAMPLE gets. `no_net` is what the example set 02_SiP gets.
RESPONSE_EXAMPLES: dict[str, dict[str, Any]] = {
    "guess": {
        "status": "guess",
        "net_range": _NET_RANGE_EXAMPLE,
        "prediction": {"m_eff": 1.425, "band_gap_k": 354.6, "fermi_energy_k": 939.8},
        "start_values": {"m_eff": 1.42, "band_gap": 355.0, "fermi_energy": 940.0},
        "warnings": [],
    },
    "no_net": {
        "status": "no_net",
        "reason": "temperature_span",
        "first_temperature_k": 308.5,
        "last_temperature_k": 650.0,
        "available_ranges": [
            {"min_temperature_k": float(low_k), "max_temperature_k": float(high_k)}
            for low_k, high_k in NET_RANGES_K
        ],
        "warnings": [],
    },
    "not_finite": {
        "status": "not_finite",
        "net_range": _NET_RANGE_EXAMPLE,
        "warnings": [],
    },
    "numerical_guess": {
        "status": "numerical_guess",
        "start_values": {"band_mass": -1.0, "fermi_energy": -700.0},
        "sign_only_parameters": ["band_mass"],
        "rmse_v_per_k": 0.0,
        "warnings": [],
    },
}


class GuessRequest(BaseModel):
    """Measured Seebeck data, in V/K, with all rows of the data.

    Unlike `POST /api/calc`, this takes every row and not only the fit range, as the desktop does.
    Rows are read in the order sent, and the choice of net reads the first and last.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [REQUEST_EXAMPLE]})

    model: str
    temperature_k: Annotated[list[PositiveFloat], Field(min_length=1)]
    seebeck_v_per_k: Annotated[list[FiniteFloat], Field(min_length=1)]

    @model_validator(mode="after")
    def _same_length(self) -> Self:
        if len(self.temperature_k) != len(self.seebeck_v_per_k):
            raise ValueError("temperature_k and seebeck_v_per_k must have the same length")
        return self


class NetRange(BaseModel):
    """The temperature span a net needs, and the range of its input."""

    min_temperature_k: float
    max_temperature_k: float


class Prediction(BaseModel):
    """The net's prediction as it is, in core units, before any rounding or limits."""

    m_eff: float
    band_gap_k: float
    fermi_energy_k: float


class GuessFound(BaseModel):
    """A guess.

    `start_values` holds what to use, by the parameter names of `GET /api/models`, in core units as
    in `core_range`: `m_eff` is dimensionless, `band_gap` and `fermi_energy` are in K. They are
    rounded and limited as the desktop's sliders do, so they lie in `core_range` of every mode of
    the model. Other parameters keep their values. With the warning `m_eff_rounds_to_zero`, `m_eff`
    is 0, which has no curve, and a fit from it fails, so a client should not use it as it is.
    """

    status: Literal["guess"]
    net_range: NetRange
    prediction: Prediction
    start_values: dict[str, float]
    warnings: list[GuessWarning]


class NumericalGuessFound(BaseModel):
    """Seebeck-only estimate; mass magnitude remains a reference value."""

    sign_only_parameters: list[str] = ["band_mass"]
    rmse_v_per_k: float
    status: Literal["numerical_guess"]
    start_values: dict[str, float]
    warnings: list[GuessWarning]


class GuessUnsupported(BaseModel):
    status: Literal["unsupported"]
    reason: Literal["sign_change", "too_few_temperatures", "zero_seebeck"]
    warnings: list[GuessWarning]


class GuessNoNet(BaseModel):
    """No net fits: the first and last rows do not span any of `available_ranges`.

    A client should keep its current values, as the desktop does.
    """

    status: Literal["no_net"]
    reason: Literal["temperature_span"]
    first_temperature_k: float
    last_temperature_k: float
    available_ranges: list[NetRange]
    warnings: list[GuessWarning]


class GuessNotFinite(BaseModel):
    """The net ran, but a value of its prediction is not finite, so there is nothing to use.

    The prediction is left out, as JSON has no such numbers. A client should keep its values.
    """

    status: Literal["not_finite"]
    net_range: NetRange
    warnings: list[GuessWarning]


GuessResponse = Annotated[
    GuessFound | NumericalGuessFound | GuessUnsupported | GuessNoNet | GuessNotFinite,
    Field(discriminator="status"),
]


def _check_model(model_id: str) -> None:
    descriptions = {description.id: description for description in registry.descriptions()}
    description = descriptions.get(model_id)
    if description is None:
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "invalid_guess",
            "Invalid request",
            [
                ErrorDetail(
                    location=["body", "model"],
                    code="unknown_model",
                    message="This model does not exist",
                )
            ],
        )
    if not description.has_initial_guess:
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "guess_unavailable",
            "This model has no neural net guess",
            [
                ErrorDetail(
                    location=["body", "model"],
                    code="no_neural_net",
                    message="See has_initial_guess in GET /api/models",
                )
            ],
        )


def _net_range(range_k: tuple[int, int]) -> NetRange:
    return NetRange(min_temperature_k=range_k[0], max_temperature_k=range_k[1])


def _warnings(outcome: GuessOutcome) -> list[GuessWarning]:
    warnings: list[GuessWarning] = []
    if outcome.unsorted_temperature:
        warnings.append("unsorted_temperature")
    if outcome.underdetermined_fit:
        warnings.append("underdetermined_fit")
    if outcome.start_values is not None and outcome.start_values["m_eff"] == 0:
        warnings.append("m_eff_rounds_to_zero")
    return warnings


def _to_response(outcome: GuessOutcome) -> GuessFound | GuessNoNet | GuessNotFinite:
    result = outcome.result
    warnings = _warnings(outcome)
    if isinstance(result, NoNeuralNet):
        return GuessNoNet(
            status="no_net",
            reason="temperature_span",
            first_temperature_k=result.first_temperature_k,
            last_temperature_k=result.last_temperature_k,
            available_ranges=[_net_range(range_k) for range_k in NET_RANGES_K],
            warnings=warnings,
        )
    if outcome.start_values is None:
        return GuessNotFinite(
            status="not_finite", net_range=_net_range(result.range_k), warnings=warnings
        )
    return GuessFound(
        status="guess",
        net_range=_net_range(result.range_k),
        prediction=Prediction(
            m_eff=result.m_eff,
            band_gap_k=result.band_gap_k,
            fermi_energy_k=result.fermi_energy_k,
        ),
        start_values=dict(outcome.start_values),
        warnings=warnings,
    )


@router.post(
    "/guess",
    response_model=GuessResponse,
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        name: {"value": example} for name, example in RESPONSE_EXAMPLES.items()
                    }
                }
            }
        },
        429: too_many_requests(),
    },
)
async def post_guess(
    body: GuessRequest, pool: CalcPoolDep, max_points: MaxPointsDep
) -> GuessFound | NumericalGuessFound | GuessUnsupported | GuessNoNet | GuessNotFinite:
    _check_model(body.model)
    if len(body.temperature_k) > max_points:
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "invalid_guess",
            "Invalid request",
            [too_many_points(max_points, ["temperature_k"])],
        )
    try:
        if registry.get(body.model).describe().initial_guess_method == "numerical":
            values = await pool.run(
                numerical_guess,
                body.model,
                np.array(body.temperature_k),
                np.array(body.seebeck_v_per_k),
            )
            if values.reason is not None:
                return GuessUnsupported(
                    status="unsupported", reason=values.reason, warnings=[*values.warnings]
                )
            return NumericalGuessFound(
                status="numerical_guess",
                start_values=values.start_values,
                warnings=[*values.warnings],
                rmse_v_per_k=values.rmse_v_per_k or 0.0,
            )
        outcome = await pool.run(
            guess, body.model, np.array(body.temperature_k), np.array(body.seebeck_v_per_k)
        )
    except CalculationFailed as error:
        log_calculation_failure(str(error))
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            "calculation_failed",
            "The calculation has no result for these parameters and temperatures",
        ) from None
    return _to_response(outcome)
