"""The interface every model implements, and the descriptions clients build their forms from.

Values in requests and results are in core units: the values the calculations take and return.
`model_scales` converts them to and from what a user sees. Convert nowhere else.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Literal, Protocol, get_args, runtime_checkable

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
    "lorenz_number",
]
FitAlgorithm = Literal["verified-sequential-v2", "legacy-sequential-v1"]
FitStatus = Literal["converged", "iteration_limit", "stopped", "failed", "stalled"]
# How a fit found each parameter, see `parameter_status`. None of these says that a value is right.
ParameterStatus = Literal[
    "fixed", "held", "estimated", "at_bound", "not_determined", "did_not_move", "not_assessed"
]
IssueSeverity = Literal["disabled", "unreliable", "caution"]
IssueCondition = Literal[
    "degeneracy_not_one",
    "collapsed_m_eff",
    "fermi_energy_in_gap",
    "fermi_energy_outside_band",
    "interpolation_extrapolated",
]

ALL_CURVE_KINDS: tuple[CurveKind, ...] = get_args(CurveKind)
NOT_PROVIDED = "not_provided"

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

    `unit` is the unit of the scaled value. `display_unit` is the one a user sees, with
    `display_factor` from the one to the other, and `display_step` the step of a control in it: an
    energy in K is shown in eV. `fit_bounds` is in core units, before any factor or transform inside
    a fit, and is None for a parameter that a fit does not change.
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
    display_unit: str | None = None
    display_factor: float = 1.0
    display_step: float | None = None

    @property
    def shown_unit(self) -> str:
        """The unit a user sees."""
        return self.unit if self.display_unit is None else self.display_unit


@dataclass(frozen=True)
class Degeneracy:
    band_1_default: float
    band_2_default: float


@dataclass(frozen=True)
class KnownIssue:
    """A known error of the calculations, and where it applies.

    `scattering` is empty for every type. `condition` limits it to some inputs. `columns` names the
    curves of a kind that it changes, and is empty for all of them. `fixed_by` is the issue that
    removes it. `affects_band_diagram` puts it on the sketch of E(k), and on nothing else.
    `explanation` is for developers, and a user sees `message_key` through i18n.
    """

    id: str
    severity: IssueSeverity
    fixed_by: str
    fit_modes: tuple[str, ...]
    explanation: str
    scattering: tuple[str, ...] = ()
    curve_kinds: tuple[CurveKind, ...] = ()
    columns: tuple[str, ...] = ()
    affects_fit: bool = False
    affects_band_diagram: bool = False
    condition: IssueCondition | None = None
    message_key: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_key", f"known_issue.{self.id}")


@dataclass(frozen=True)
class UnavailableCurve:
    """A kind of curve a mode does not offer, and a code that says why."""

    kind: CurveKind
    reason: str


@dataclass(frozen=True)
class FitStage:
    """One solver run of a fit: the quantity it fits, and the parameters it finds.

    `repeats` marks a stage of the loop of an iterative mode, which runs once in each iteration.
    `parameters` names every parameter the stage can find; the scattering decides which of them
    a fit has.
    """

    quantity: Quantity
    parameters: tuple[str, ...]
    repeats: bool = False


@dataclass(frozen=True)
class FitMode:
    """One way of fitting a model: which data it needs, its parameters, and the curves it offers.

    `scattering` is empty when the mode has no choice of scattering. `iterative` tells a client
    whether an iteration count means anything for this mode.

    `unavailable_curves` says why a kind is missing from `curve_kinds`, and a kind in neither has
    the reason `not_provided`. `relative_curve_kinds` names curves whose size rests on an assumed
    value rather than on data, such as carrier concentrations with no Hall data to set m1.

    `stages` are the solver runs of a fit, in their order, as `fit_module` runs them.

    `band_2_edge` names the parameter whose value in core units is the edge of band 2, in K,
    measured from that of band 1, so that a client can draw it without knowing a model's names.
    A mode with one band has none.
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
    known_issues: tuple[KnownIssue, ...] = ()
    unavailable_curves: tuple[UnavailableCurve, ...] = ()
    relative_curve_kinds: tuple[CurveKind, ...] = ()
    stages: tuple[FitStage, ...] = ()
    band_2_edge: str | None = None

    def unavailable_reason(self, kind: CurveKind) -> str | None:
        """Return why this mode does not offer a kind of curve, or None if it does."""
        if kind in self.curve_kinds:
            return None
        for unavailable in self.unavailable_curves:
            if unavailable.kind == kind:
                return unavailable.reason
        return NOT_PROVIDED

    @property
    def disabled(self) -> bool:
        """Whether a client must not offer this mode. The model does not enforce this itself."""
        return any(issue.severity == "disabled" for issue in self.known_issues)

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
    # Whether initial estimates are available (DPB neural net or SPB numerical search).
    has_initial_guess: bool = False
    initial_guess_method: str | None = None

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

    def check(self, quantity: str) -> None:
        """Raise `ValueError` unless this is usable data: arrays of finite numbers, T above 0."""
        for array in (self.temperature_k, self.values):
            if not isinstance(array, np.ndarray) or array.ndim != 1 or array.size == 0:
                raise ValueError(f"Measurement {quantity} needs non-empty one-dimensional arrays")
            if not np.issubdtype(array.dtype, np.number) or not np.all(np.isfinite(array)):
                raise ValueError(f"Measurement {quantity} needs finite numbers")
        if self.temperature_k.size != self.values.size:
            raise ValueError(f"Measurement {quantity} has arrays of different lengths")
        if np.min(self.temperature_k) <= 0:
            raise ValueError(f"Measurement {quantity} needs temperatures above 0 K")


BandConfiguration = Literal["vb_vb", "vb_cb", "cb_cb"]
DpbParameterization = Literal["legacy_fermi", "explicit_density_v1", "explicit_fermi_v1"]
CarrierType = Literal["p", "n"]


@dataclass(frozen=True)
class ExplicitBands:
    band_configuration: BandConfiguration
    net_electron_density_per_m3: float | None = None
    carrier_type: CarrierType | None = None

    def __post_init__(self) -> None:
        d = self.net_electron_density_per_m3
        if self.carrier_type is not None:
            if (
                self.band_configuration not in get_args(BandConfiguration)
                or self.carrier_type not in get_args(CarrierType)
                or d is not None
            ):
                raise ValueError("Fermi-energy bands require a carrier type and no fixed density")
            if (self.band_configuration == "cb_cb" and self.carrier_type != "n") or (
                self.band_configuration == "vb_vb" and self.carrier_type != "p"
            ):
                raise ValueError("Carrier type is incompatible with the band configuration")
            return
        if (
            self.band_configuration not in get_args(BandConfiguration)
            or d is None
            or not isfinite(d)
        ):
            raise ValueError("The band configuration and finite carrier excess are required")
        if self.band_configuration == "cb_cb" and d <= 0:
            raise ValueError("Two conduction bands require n − p > 0")
        if self.band_configuration == "vb_vb" and d >= 0:
            raise ValueError("Two valence bands require n − p < 0")


@dataclass(frozen=True, eq=False)
class CurveRequest:
    """Ask for curves. `parameters` holds every parameter of the mode, in core units.

    That includes fixed parameters and those of other scattering types, which the calculations
    read and return unchanged. `extrapolated` says that the data behind it were partly made up.
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
    extrapolated: bool = False
    explicit_bands: ExplicitBands | None = None


@dataclass(frozen=True)
class BandDiagramRequest:
    """Ask for the sketch of E(k). `parameters` holds every parameter of the mode, in core units."""

    fit_mode: str
    parameters: Mapping[str, float]
    band_1_degeneracy: float = 1.0
    band_2_degeneracy: float = 1.0
    explicit_bands: ExplicitBands | None = None


@dataclass(frozen=True, eq=False)
class BandDiagramResult:
    """Curves over `wavevector`, by name, where each name ends in its unit.

    `wavevector` has no unit, as the formula states none (`band_diagram_formula`).
    """

    wavevector: np.ndarray
    curves: Mapping[str, np.ndarray]
    known_issues: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class CurveResult:
    """Curves by name, where each name ends in its unit, such as `seebeck_v_per_k`."""

    temperature_k: np.ndarray
    curves: Mapping[str, np.ndarray]
    known_issues: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class FitRequest:
    """Ask for a fit. `start` holds every parameter of the mode, in core units.

    That includes fixed parameters and those of other scattering types. `bounds` overrides
    the bounds of the description for the fitted parameters it names, and naming any other is an
    error. `extrapolated` says that interpolation made up some of the data, so that the result says
    so too.

    `held` names fitted parameters that keep their start values: each solver run fits only the
    others, and a run with none left is skipped. Naming a parameter the mode does not fit, or every
    one it fits, is an error. The default algorithm verifies conditional stage optima;
    legacy-sequential-v1 explicitly selects the historical desktop estimator.
    """

    fit_mode: str
    measurements: Mapping[Quantity, Measurement]
    start: Mapping[str, float]
    bounds: Mapping[str, Bounds] = field(default_factory=dict)
    scattering: str | None = None
    band_1_degeneracy: float = 1.0
    band_2_degeneracy: float = 1.0
    extrapolated: bool = False
    held: frozenset[str] = frozenset()
    algorithm: FitAlgorithm = "verified-sequential-v2"
    explicit_bands: ExplicitBands | None = None


@dataclass(frozen=True)
class ResidualDiagnostics:
    rmse: float
    relative_l2: float | None
    unit: str


@dataclass(frozen=True)
class FitDiagnostics:
    """Numerical diagnostics, separate from physical adequacy and uncertainty.

    `optimality` is the normalized projected gradient at the returned parameters,
    in scaled stage coordinates. Conditional objective-reduction audits also have
    to pass before `stage_consistent` can be true.
    """

    termination: str
    stage_consistent: bool
    objectives: Mapping[str, float]
    optimality: Mapping[str, float]
    evaluations: int
    recoveries: int
    residuals: Mapping[Quantity, ResidualDiagnostics]
    unidentified: tuple[str, ...]
    uncertainty: Literal["not_assessed"] = "not_assessed"
    residual_adequacy: Literal["not_assessed"] = "not_assessed"


@dataclass(frozen=True)
class FitResult:
    """The outcome of a fit, in core units.

    A fit that fails returns `failed` with a `message`, and its start values, because partial values
    should not look usable. A request that is invalid raises instead. `stopped` holds the values of
    the last iteration, with m1 still at its start, and `iteration_limit` holds what the fit ended
    with, which is not a converged result.

    For legacy-sequential-v1, `converged` means that the historical stop rule was met.
    For verified-sequential-v2 it requires conditional stage optimality at the same returned
    vector. `stalled` retains a usable endpoint without that certificate. Neither status is
    evidence of physical adequacy or identifiability; consult typed diagnostics.

    `iterations` counts completed iterations, and is None for a single-pass mode. A fitted value can
    lie outside the range of its control. `message` holds fixed text with no measured values.

    `parameter_errors` holds standard errors from the last solver run of each stage. It leaves out a
    parameter with an error that is not finite, or is exactly 0, which means the data do not
    determine it. Each error holds every other stage fixed, so in a staged fit it can be far too
    small, and it is not a plain uncertainty to show as a value with a +/-.

    `at_bounds` names fitted parameters that ended at a bound, so the bound may be what set them. A
    parameter a fit never reached, such as m1 in a stopped fit, is not named.

    `held` names the parameters the request held at their start values, which are in `parameters`
    exactly as sent, and in neither `parameter_errors` nor `at_bounds`.

    `last_changes` holds, for an iterative legacy fit, the relative change of each parameter of
    its loop in the last iteration, as its stop rule compared it with `FitMode.threshold`: the
    first iteration compares with the start values, and a change that is not finite is inf. The
    rule stops the loop only when every one is at most the threshold. With N2/N1 other than 1, the
    first change of m_eff compares with its start divided by N2/N1, so it reads too large (D12,
    #85). At the iteration limit the loop fits S once more after these changes, so m_eff, E_g and
    E_F are from that stage. It is empty otherwise.

    `parameter_status` says, for each parameter in `parameters`, how the fit found it, from the
    signals the fit has. See `seeband_core.parameter_status`. `estimated` means only that no signal
    said otherwise, not that the data determine the value or that it is right. The uncertainty of
    the values is not assessed yet (#182).
    """

    parameters: Mapping[str, float]
    status: FitStatus
    iterations: int | None = None
    message: str | None = None
    parameter_errors: Mapping[str, float] = field(default_factory=dict)
    at_bounds: tuple[str, ...] = ()
    known_issues: tuple[str, ...] = ()
    held: tuple[str, ...] = ()
    algorithm: FitAlgorithm = "legacy-sequential-v1"
    diagnostics: FitDiagnostics | None = None
    parameter_status: Mapping[str, ParameterStatus] = field(default_factory=dict)
    last_changes: Mapping[str, float] = field(default_factory=dict)


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

    def band_diagram(self, request: BandDiagramRequest) -> BandDiagramResult: ...

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        """Run a fit. The callback is apart from the request, which stays picklable for a worker.

        The callback runs once per iteration of an iterative mode, and never for a single-pass mode.
        An error it raises other than `FitStopped` reaches the caller.
        """
        ...
