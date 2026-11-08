"""Checks that `POST /api/calc` and `POST /api/fit` share, against a model's description."""

from http import HTTPStatus
from typing import Annotated, Self

import numpy as np
from fastapi import Depends, Request
from pydantic import BaseModel, Field, model_validator
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitMode, Measurement, ModelDescription, Quantity

from seeband_api.errors import ApiError, ErrorDetail

# Strict, so that `true` or "1.5" are refused here as the contract and the mock refuse them.
FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]


class MeasurementInput(BaseModel):
    """Measured points, with values in V/K for S, ohm m for rho and m^3/C for R_H."""

    temperature_k: Annotated[list[PositiveFloat], Field(min_length=1)]
    values: Annotated[list[FiniteFloat], Field(min_length=1)]

    @model_validator(mode="after")
    def _same_length(self) -> Self:
        if len(self.temperature_k) != len(self.values):
            raise ValueError("temperature_k and values must have the same length")
        return self


def _get_max_points(request: Request) -> int:
    max_points: int = request.app.state.settings.max_points
    return max_points


MaxPointsDep = Annotated[int, Depends(_get_max_points)]


def too_many_points(max_points: int, location: list[str | int]) -> ErrorDetail:
    return invalid("too_many_points", f"At most {max_points} points", location)


def check_point_counts(
    measurements: dict[Quantity, MeasurementInput], max_points: int
) -> list[ErrorDetail]:
    """Counts what a client sent, rather than what lies in its fit range, as all of it is parsed."""
    return [
        too_many_points(max_points, ["measurements", quantity])
        for quantity, measurement in measurements.items()
        if len(measurement.temperature_k) > max_points
    ]


def invalid(code: str, message: str, location: list[str | int]) -> ErrorDetail:
    return ErrorDetail(location=["body", *location], code=code, message=message)


def find_mode(
    model_id: str, fit_mode_id: str, error_code: str, error_message: str
) -> tuple[ModelDescription, FitMode]:
    """Finds a mode that can run, or refuses with this error or as disabled."""
    descriptions = {description.id: description for description in registry.descriptions()}
    description = descriptions.get(model_id)
    if description is None:
        detail = invalid("unknown_model", "This model does not exist", ["model"])
        raise ApiError(HTTPStatus.UNPROCESSABLE_CONTENT, error_code, error_message, [detail])
    try:
        fit_mode = description.fit_mode(fit_mode_id)
    except KeyError:
        detail = invalid("unknown_fit_mode", "This model has no such fit mode", ["fit_mode"])
        raise ApiError(
            HTTPStatus.UNPROCESSABLE_CONTENT, error_code, error_message, [detail]
        ) from None
    if fit_mode.disabled:
        raise ApiError(
            HTTPStatus.CONFLICT,
            "fit_mode_disabled",
            "This fit mode is disabled until its known issue is fixed",
            [
                invalid(issue.id, "A known issue disables this mode", ["fit_mode"])
                for issue in fit_mode.known_issues
                if issue.severity == "disabled"
            ],
        )
    return description, fit_mode


def check_scattering(scattering: str | None, fit_mode: FitMode) -> list[ErrorDetail]:
    if scattering is None:
        if fit_mode.scattering:
            return [invalid("missing_scattering", "This mode needs one", ["scattering"])]
    elif scattering not in fit_mode.scattering:
        return [invalid("unknown_scattering", "This mode has no such type", ["scattering"])]
    return []


def check_degeneracy(band_1: float, band_2: float, fit_mode: FitMode) -> list[ErrorDetail]:
    if fit_mode.degeneracy is not None and fit_mode.degeneracy.band_2_default is not None:
        return []
    return [
        invalid("degeneracy_not_in_mode", "This mode has no band degeneracy", [field])
        for field, value in (("band_1_degeneracy", band_1), ("band_2_degeneracy", band_2))
        if value != 1 and (field == "band_2_degeneracy" or fit_mode.degeneracy is None)
    ]


def check_parameter_names(names: list[str], field: str, fit_mode: FitMode) -> list[ErrorDetail]:
    """Every parameter of a mode is needed, including those of other scattering types."""
    expected = {spec.name for spec in fit_mode.parameters}
    missing = [
        invalid("missing_parameter", "This mode needs it", [field, spec.name])
        for spec in fit_mode.parameters
        if spec.name not in names
    ]
    unknown = [
        invalid("unknown_parameter", "This mode has no such parameter", [field, name])
        for name in names
        if name not in expected
    ]
    return missing + unknown


def to_measurements(
    measurements: dict[Quantity, MeasurementInput],
) -> dict[Quantity, Measurement]:
    return {
        quantity: Measurement(np.array(measurement.temperature_k), np.array(measurement.values))
        for quantity, measurement in measurements.items()
    }
