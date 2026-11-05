"""The interface every model implements, and the descriptions clients build their forms from.

Values in requests and results are in core units: the values the calculations take and return.
`model_scales` converts them to and from what a user sees. Convert nowhere else.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np

Quantity = Literal["seebeck", "resistivity", "hall"]
ParameterRole = Literal["fitted", "fixed"]
CurveKind = Literal[
    "measured",
    "seebeck",
    "seebeck_by_band",
    "chemical_potential",
    "electrical_conductivity",
    "electrical_conductivity_by_band",
    "thermal_conductivity",
    "carrier_concentration_by_band",
]
FitStatus = Literal["converged", "iteration_limit", "stopped", "failed"]

QUANTITY_UNITS: Mapping[Quantity, str] = {
    "seebeck": "V/K",
    "resistivity": "ohm m",
    "hall": "m^3/C",
}


@dataclass(frozen=True)
class Bounds:
    lower: float
    upper: float


@dataclass(frozen=True)
class ValueRange:
    """The range of a parameter's control, which limits its input but not a fitted result."""

    minimum: float
    maximum: float
    step: float
    default: float


@dataclass(frozen=True)
class ParameterSpec:
    """One parameter of a fit mode.

    `value_range` is in control units. `display_scale` converts these to the value a user sees,
    and `fit_scale` to core units. `calc_scale` records what the desktop's slider passes to a curve;
    use it only to reproduce that path, because results of a fit go to curves unchanged.

    `unit` is the unit of the value a user sees. `fit_bounds` is in core units, before any factor
    or transform inside a fit, and is None for a parameter that a fit does not change.
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
class Degeneracy:
    band_1_default: float
    band_2_default: float


@dataclass(frozen=True)
class FitMode:
    """One way of fitting a model: which data it needs, its parameters, and the curves it offers.

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
    degeneracy: Degeneracy | None = None
    curve_kinds: tuple[CurveKind, ...] = ("measured",)

    def parameters_for(self, scattering: str | None) -> tuple[ParameterSpec, ...]:
        """Return the parameters that apply to a scattering type, or all of them for None."""
        if scattering is None:
            return self.parameters
        if scattering not in self.scattering:
            raise ValueError(f"Fit mode {self.id} has no scattering type {scattering}")
        return tuple(
            spec for spec in self.parameters if not spec.scattering or scattering in spec.scattering
        )


@dataclass(frozen=True)
class ModelDescription:
    id: str
    name: str
    fit_modes: tuple[FitMode, ...]
    default_min_temperature_k: float
    default_max_temperature_k: float
    default_curve_points: int

    def fit_mode(self, fit_mode_id: str) -> FitMode:
        for fit_mode in self.fit_modes:
            if fit_mode.id == fit_mode_id:
                return fit_mode
        raise KeyError(f"Model {self.id} has no fit mode {fit_mode_id}")


@dataclass(frozen=True, eq=False)
class Measurement:
    """Measured values in the unit of `QUANTITY_UNITS` for their quantity."""

    temperature_k: np.ndarray
    values: np.ndarray


@dataclass(frozen=True, eq=False)
class CurveRequest:
    """Ask for curves. `parameters` holds every parameter of the mode, in core units.

    That includes fixed parameters and those of other scattering types, which the calculations
    read and return unchanged.
    """

    fit_mode: str
    parameters: Mapping[str, float]
    min_temperature_k: float
    max_temperature_k: float
    points: int
    scattering: str | None = None
    kind: CurveKind = "measured"
    band_1_degeneracy: float = 1.0
    band_2_degeneracy: float = 1.0


@dataclass(frozen=True, eq=False)
class CurveResult:
    """Curves by name, where each name ends in its unit, such as `seebeck_v_per_k`."""

    temperature_k: np.ndarray
    curves: Mapping[str, np.ndarray]


@dataclass(frozen=True, eq=False)
class FitRequest:
    """Ask for a fit. `start` holds every parameter of the mode, in core units.

    That includes fixed parameters and those of other scattering types. `bounds` overrides
    the bounds of the description for the fitted parameters it names, and naming any other is an
    error.
    """

    fit_mode: str
    measurements: Mapping[Quantity, Measurement]
    start: Mapping[str, float]
    bounds: Mapping[str, Bounds] = field(default_factory=dict)
    scattering: str | None = None
    band_1_degeneracy: float = 1.0
    band_2_degeneracy: float = 1.0


@dataclass(frozen=True)
class FitResult:
    """The outcome of a fit, in core units.

    A fit that fails returns `failed` with a `message`, and its start values, because partial values
    should not look usable. A request that is invalid raises instead. `stopped` holds the values of
    the last iteration, with m1 still at its start, and `iteration_limit` holds what the fit ended
    with, which is not a converged result.

    `converged` means that the fit ended normally: for an iterative fit, its stop rule was met, and
    for a single-pass fit, the solver returned. It does not mean the result is sound.

    `iterations` counts completed iterations, and is None for a single-pass mode. A fitted value can
    lie outside the range of its control. `message` holds fixed text with no measured values.
    """

    parameters: Mapping[str, float]
    status: FitStatus
    iterations: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class IterationUpdate:
    """Progress of an iterative fit, in core units, in the form a final result would have.

    Raise `FitStopped` from a callback to stop. A parameter fitted after the loop, such as m1, keeps
    its start value here.
    """

    iteration: int
    parameters: Mapping[str, float]


class FitStopped(Exception):
    """Raised by an iteration callback to stop a fit."""


IterationCallback = Callable[[IterationUpdate], None]


@runtime_checkable
class Model(Protocol):
    def describe(self) -> ModelDescription: ...

    def calculate(self, request: CurveRequest) -> CurveResult: ...

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        """Run a fit. The callback is apart from the request, which stays picklable for a worker.

        The callback runs once per iteration of an iterative mode, and never for a single-pass mode.
        An error it raises other than `FitStopped` reaches the caller.
        """
        ...
