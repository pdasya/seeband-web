"""The interface every model implements, and the descriptions clients build their forms from."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np

Quantity = Literal["seebeck", "resistivity", "hall"]
ParameterRole = Literal["fitted", "fixed"]


@dataclass(frozen=True)
class Bounds:
    lower: float
    upper: float


@dataclass(frozen=True)
class ValueRange:
    """The range of a parameter's control. Multiply by a scale to get a value in other units."""

    minimum: float
    maximum: float
    step: float
    default: float


@dataclass(frozen=True)
class ParameterSpec:
    """One parameter of a fit mode.

    `value_range` is in control units. `display_scale` converts these to the value a user sees,
    `fit_scale` to the start value of a fit, and `calc_scale` to the value a curve receives.
    `fit_bounds` is in the units of the fit, and is None for a parameter that a fit does not change.
    """

    name: str
    meaning: str
    unit: str
    role: ParameterRole
    scattering: tuple[str, ...]
    value_range: ValueRange
    display_scale: float
    fit_scale: float
    calc_scale: float
    fit_bounds: Bounds | None = None
    bounds_editable: bool = False


@dataclass(frozen=True)
class FitMode:
    """One way of fitting a model: which data it needs and which parameters it has.

    `scattering` is empty when the mode has no choice of scattering. `iterative` tells a client
    whether an iteration count means anything for this mode.
    """

    id: str
    quantities: tuple[Quantity, ...]
    parameters: tuple[ParameterSpec, ...]
    scattering: tuple[str, ...] = ()
    default_scattering: str | None = None
    iterative: bool = False
    threshold: float | None = None
    max_iterations: int | None = None
    uses_degeneracy: bool = False

    def parameters_for(self, scattering: str | None) -> tuple[ParameterSpec, ...]:
        """Return the parameters that apply to a scattering type, or all of them for None."""
        if scattering is None:
            return self.parameters
        return tuple(spec for spec in self.parameters if scattering in spec.scattering)


@dataclass(frozen=True)
class ModelDescription:
    id: str
    name: str
    fit_modes: tuple[FitMode, ...]

    def fit_mode(self, fit_mode_id: str) -> FitMode:
        for fit_mode in self.fit_modes:
            if fit_mode.id == fit_mode_id:
                return fit_mode
        raise KeyError(f"Model {self.id} has no fit mode {fit_mode_id}")


@dataclass(frozen=True, eq=False)
class Measurement:
    temperature_k: np.ndarray
    values: np.ndarray


@dataclass(frozen=True)
class CurveRequest:
    fit_mode: str
    parameters: Mapping[str, float]
    min_temperature_k: float
    max_temperature_k: float
    points: int
    scattering: str | None = None
    degeneracy_ratio: float = 1.0


@dataclass(frozen=True, eq=False)
class CurveResult:
    temperature_k: np.ndarray
    curves: Mapping[Quantity, np.ndarray]


@dataclass(frozen=True)
class FitRequest:
    fit_mode: str
    measurements: Mapping[Quantity, Measurement]
    start: Mapping[str, float]
    bounds: Mapping[str, Bounds] = field(default_factory=dict)
    scattering: str | None = None
    degeneracy_ratio: float = 1.0


@dataclass(frozen=True)
class FitResult:
    parameters: Mapping[str, float]


@runtime_checkable
class Model(Protocol):
    def describe(self) -> ModelDescription: ...

    def calculate(self, request: CurveRequest) -> CurveResult: ...

    def fit(self, request: FitRequest) -> FitResult: ...
