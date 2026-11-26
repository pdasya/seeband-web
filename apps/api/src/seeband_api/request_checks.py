"""Checks that `POST /api/calc` and `POST /api/fit` share, against a model's description."""

from collections.abc import Callable, Sized
from http import HTTPStatus
from typing import Annotated, Any, ClassVar, Self, get_args

import numpy as np
from fastapi import Depends, Request
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from pydantic_core import PydanticCustomError
from seeband_core.model_catalog import registry
from seeband_core.model_descriptions import explicit_dpb_description
from seeband_core.model_interface import (
    BandConfiguration,
    CarrierType,
    DpbParameterization,
    ExplicitBands,
    FitMode,
    Measurement,
    ModelDescription,
    Quantity,
)

from seeband_api.errors import ApiError, ErrorDetail
from seeband_api.settings import MAX_LISTED_POINTS

# Strict, so that `true` or "1.5" are refused here as the contract and the mock refuse them.
FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]

# Hard bounds on what a request can list, whatever the settings, so that a large invalid body costs
# little: `MAX_LISTED_POINTS` is 50 times the default `max_points`, which no setting can pass.
# A list also stops at its first wrong value, so it gives one error, not one for each value.
# More than any mode has parameters.
MAX_PARAMETERS = 64


def _at_most(count: int) -> Callable[[Any], Any]:
    """Refuses a list or dict longer than `count` before its items are read, which pydantic's own
    `max_length` does only after them, giving an error for each item first."""

    def check(value: Any) -> Any:
        if isinstance(value, Sized) and not isinstance(value, str) and len(value) > count:
            raise PydanticCustomError(
                "too_long", "At most {max_length} items", {"max_length": count}
            )
        return value

    return check


def bounded(count: int, *, min_length: int = 0, fail_fast: bool = False) -> tuple[Any, ...]:
    """Metadata for a list or dict of at most `count` items, checked before its items."""
    return (
        Field(min_length=min_length, max_length=count, fail_fast=fail_fast or None),
        BeforeValidator(_at_most(count)),
    )


PointList = Annotated[
    list[PositiveFloat], *bounded(MAX_LISTED_POINTS, min_length=1, fail_fast=True)
]
ValueList = Annotated[list[FiniteFloat], *bounded(MAX_LISTED_POINTS, min_length=1, fail_fast=True)]
ParameterValues = Annotated[dict[str, FiniteFloat], *bounded(MAX_PARAMETERS)]


class BandInputs(BaseModel):
    requires_transport_fermi: ClassVar[bool] = True

    model: str
    parameterization: DpbParameterization = "legacy_fermi"
    band_configuration: BandConfiguration | None = None
    net_electron_density_per_m3: FiniteFloat | None = None
    carrier_type: CarrierType | None = None

    def explicit_settings(self) -> ExplicitBands | None:
        if self.parameterization == "legacy_fermi":
            if any(
                value is not None
                for value in (
                    self.band_configuration,
                    self.net_electron_density_per_m3,
                    self.carrier_type,
                )
            ):
                raise ValueError("Band configuration and carrier inputs require explicit DPB")
            return None
        if self.model != "dpb" or self.band_configuration is None:
            raise ValueError("Explicit DPB needs a band configuration")
        if self.parameterization == "explicit_fermi_v1":
            if self.net_electron_density_per_m3 is not None:
                raise ValueError("Fermi-energy DPB requires no fixed density")
            return ExplicitBands(self.band_configuration, carrier_type=self.carrier_type)
        if self.net_electron_density_per_m3 is None or self.carrier_type is not None:
            raise ValueError("Density DPB needs signed density in m⁻³ and no carrier_type")
        return ExplicitBands(self.band_configuration, self.net_electron_density_per_m3)

    @model_validator(mode="after")
    def _check_band_inputs(self) -> Self:
        settings = self.explicit_settings()
        if settings is not None:
            for name in ("band_1_degeneracy", "band_2_degeneracy"):
                value = getattr(self, name, 1.0)
                if not float(value).is_integer():
                    raise ValueError(f"{name} must be a positive integer for explicit bands")
            values = getattr(self, "parameters", None) or getattr(self, "start", {})
            if getattr(self, "scattering", None) == "ionized" and values.get("B", 1) < 0:
                raise ValueError("The ionized relative weight B must be nonnegative")
            for name in ("m1", "mass_ratio"):
                if name in values and values[name] <= 0:
                    raise ValueError(f"{name} must be positive in explicit DPB")
            if (
                self.requires_transport_fermi
                and settings.uses_fermi_energy
                and {"m1", "mass_ratio", "band_offset_k", "fermi_energy"} <= values.keys()
            ):
                from seeband_core.explicit_transport import density_settings
                from seeband_core.math_module import NoFiniteChemicalPotentialError

                try:
                    density_settings(
                        settings,
                        values,
                        getattr(self, "band_1_degeneracy", 1.0),
                        getattr(self, "band_2_degeneracy", 1.0),
                    )
                except NoFiniteChemicalPotentialError as exc:
                    if exc.code is None:
                        raise
                    raise PydanticCustomError(exc.code, exc.reason) from exc
            for name in ("band_1_degeneracy", "band_2_degeneracy"):
                if name in type(self).model_fields and name not in self.model_fields_set:
                    raise ValueError(
                        f"Supply {name} explicitly for the selected band configuration"
                    )
        return self


class MeasurementInput(BaseModel):
    """Measured points, with values in V/K for S, ohm m for rho and m^3/C for R_H."""

    temperature_k: PointList
    values: ValueList

    @model_validator(mode="after")
    def _same_length(self) -> Self:
        if len(self.temperature_k) != len(self.values):
            raise ValueError("temperature_k and values must have the same length")
        return self


# One entry for each quantity at most, whichever they are.
Measurements = Annotated[dict[Quantity, MeasurementInput], *bounded(len(get_args(Quantity)))]


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
    model_id: str,
    fit_mode_id: str,
    error_code: str,
    error_message: str,
    explicit: ExplicitBands | None = None,
) -> tuple[ModelDescription, FitMode]:
    """Finds a mode that can run, or refuses with this error or as disabled."""
    descriptions = {description.id: description for description in registry.descriptions()}
    description = descriptions.get(model_id)
    if description is None:
        detail = invalid("unknown_model", "This model does not exist", ["model"])
        raise ApiError(HTTPStatus.UNPROCESSABLE_CONTENT, error_code, error_message, [detail])
    if explicit is not None:
        description = explicit_dpb_description(explicit.uses_fermi_energy)
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
        if fit_mode.scattering and fit_mode.id not in ("spb_s", "dpb_s"):
            return [invalid("missing_scattering", "This mode needs one", ["scattering"])]
    elif scattering not in fit_mode.scattering:
        return [invalid("unknown_scattering", "This mode has no such type", ["scattering"])]
    return []


def check_degeneracy(band_1: float, band_2: float, fit_mode: FitMode) -> list[ErrorDetail]:
    if fit_mode.degeneracy is not None:
        return []
    return [
        invalid("degeneracy_not_in_mode", "This mode has no band degeneracy", [field])
        for field, value in (("band_1_degeneracy", band_1), ("band_2_degeneracy", band_2))
        if value != 1
    ]


def check_parameter_names(
    names: list[str], field: str, fit_mode: FitMode, scattering: str | None = None
) -> list[ErrorDetail]:
    """Accept historical full vectors. Only mixed transport requires its C/D crossovers."""
    expected = {spec.name for spec in fit_mode.parameters}
    for law, overrides in fit_mode.parameter_overrides:
        if scattering is None or scattering == law:
            expected.update(spec.name for spec in overrides)
    missing = [
        invalid("missing_parameter", "This mode needs it", [field, spec.name])
        for spec in fit_mode.parameters
        if spec.name not in names and (scattering == "acPhDis" or spec.scattering != ("acPhDis",))
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
