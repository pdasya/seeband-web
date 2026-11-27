"""SPB and DPB behind the model interface, with the numbers of the ported calculations.

Everything here is in core units, so nothing here converts a scale. Results keep the order of the
calculations they come from.
"""

import dataclasses
import functools
import logging
import math
import traceback
from collections.abc import Callable, Iterable, Mapping
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np

from seeband_core import fit_module
from seeband_core import math_module as _CORE_MATH
from seeband_core.known_issues import (
    active_issue_ids,
    band_diagram_issue_ids,
    disabled_issue_ids,
)
from seeband_core.math_module import ChemicalPotentialError, reuse_chemical_potential
from seeband_core.model_descriptions import (
    DPB_BANDS as _DPB_BANDS,
)
from seeband_core.model_descriptions import (
    DPB_SCATTERING as _DPB_SCATTERING,
)
from seeband_core.model_descriptions import (
    SPB_SCATTERING as _SPB_SCATTERING,
)
from seeband_core.model_descriptions import (
    explicit_dpb_description,
    load_desktop_descriptions,
)
from seeband_core.model_interface import (
    BandDiagramRequest,
    BandDiagramResult,
    Bounds,
    CurveKind,
    CurveRequest,
    CurveResult,
    ExplicitBands,
    FitMode,
    FitRequest,
    FitResult,
    FitStatus,
    FitStopped,
    IterationCallback,
    IterationUpdate,
    Measurement,
    ModelDescription,
    Quantity,
)
from seeband_core.parameter_status import parameter_statuses

# Any, because calls here spread lists of mixed arguments that mypy cannot match to a signature.
_CORE: Any = fit_module.PB_fit()
logger = logging.getLogger(__name__)
_MEASURED_CURVES = ("seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c")
# A parameter this close to a bound, as a share of the bound, counts as being at it. A share of the
# range would flag well-fitted values on the ranges here that span many decades.
AT_BOUND_TOLERANCE = 1e-6
# The key of each stage in `fit_module.FitProgress`.
_STAGE_KEYS: dict[Quantity, str] = {"seebeck": "see", "resistivity": "res", "hall": "hall"}
_CURVE_NAMES: dict[CurveKind, tuple[str, ...]] = {
    "seebeck": ("seebeck_v_per_k",),
    "seebeck_by_band": ("seebeck_band_1_v_per_k", "seebeck_band_2_v_per_k"),
    "chemical_potential": ("chemical_potential_k",),
    "electrical_conductivity": ("electrical_conductivity_s_per_m",),
    "electrical_conductivity_by_band": (
        "electrical_conductivity_band_1_s_per_m",
        "electrical_conductivity_band_2_s_per_m",
    ),
    "thermal_conductivity": ("thermal_conductivity_w_per_m_k",),
    "carrier_concentration_by_band": (
        "carrier_concentration_band_1_per_cm3",
        "carrier_concentration_band_2_per_cm3",
    ),
}
# L = κ_e/(σT), and for two bands each band's own L, which κ_e weighs by its σ.
LORENZ_CURVE = "lorenz_number_w_ohm_per_k2"
LORENZ_BAND_CURVES = (
    "lorenz_number_band_1_w_ohm_per_k2",
    "lorenz_number_band_2_w_ohm_per_k2",
)


def parabolic_band(
    min_wavevector: float, max_wavevector: float, points: int, mass: float, energy: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return wavevectors in nm^-1 and energies in K for a signed mass in m_e."""
    wavevector, band_energy = _CORE.get_parabolic_band(
        min_wavevector, max_wavevector, points, mass, energy
    )
    return wavevector, band_energy


_DIAGRAM_K_RANGE_NM_INV = (-2.0, 2.0)
_DIAGRAM_POINTS = 101


def _values(parameters: Mapping[str, float], names: Iterable[str]) -> list[float]:
    names = list(names)
    missing = [name for name in names if name not in parameters and name not in ("C", "D")]
    if missing:
        raise ValueError(f"Missing parameters: {missing}")
    return [parameters.get(name, 0.0) for name in names]


def _value(parameters: Mapping[str, float], name: str) -> float:
    return _values(parameters, [name])[0]


def _degeneracy_ratio(request: CurveRequest | FitRequest) -> float:
    for degeneracy in (request.band_1_degeneracy, request.band_2_degeneracy):
        if not 0 < degeneracy < math.inf:
            raise ValueError("Band degeneracies must be positive")
    return request.band_2_degeneracy / request.band_1_degeneracy


def _mode_degeneracy_ratio(request: CurveRequest | FitRequest, fit_mode: FitMode) -> float:
    """N₂/N₁ for a two-band mode, and 1 for one band."""
    return _degeneracy_ratio(request) if fit_mode.degeneracy is not None else 1.0


# The mechanisms whose band weights the Lorenz moments know.
_MOMENT_SCATTERING = frozenset({None, "acPh", "dis", "acPhDis"})


def _amplitude_name(scattering: str | None) -> str:
    """The conductivity amplitude of a mechanism: F for alloy disorder, A otherwise."""
    return "F" if scattering == "dis" else "A"


def _measurement_arrays(
    measurements: Mapping[Quantity, Measurement], quantities: Iterable[Quantity]
) -> list[Any]:
    """Each quantity's temperatures and values, in ascending order of temperature.

    The chemical potential is solved from one temperature to the next, starting each from the root
    of the one before, which can miss the root on a step down to a much lower temperature. Files
    come sorted (D22), and an API client's order now gives the same fit. Least squares does not
    depend on the order of the points, so sorted data fit as before.
    """
    arrays: list[Any] = []
    for quantity in quantities:
        if quantity not in measurements:
            raise ValueError(f"Missing measurement: {quantity}")
        measurement = measurements[quantity]
        temperatures, values = measurement.temperature_k, measurement.values
        if np.any(np.diff(temperatures) < 0):
            order = np.argsort(temperatures, kind="stable")
            temperatures, values = temperatures[order], values[order]
        arrays += [temperatures, values]
    return arrays


def _standard_errors(covariance: np.ndarray) -> list[float]:
    """Return the standard error of each value, with NaN where the covariance gives none."""
    with np.errstate(invalid="ignore"):
        errors = np.sqrt(np.diag(covariance))
    return [float(error) if np.isfinite(error) else math.nan for error in errors]


def _named_errors(names: Iterable[str], errors: Iterable[float]) -> dict[str, float]:
    """Each stage parameter's error, usable or not, see `_usable_error`."""
    return dict(zip(names, errors, strict=True))


def _last_changes(
    fit_mode: FitMode, scattering: str | None, progress: fit_module.FitProgress
) -> dict[str, float]:
    """Each loop parameter's change in the last iteration, as the legacy stop rule compared it.

    The loop orders its changes as the Seebeck and then the resistivity stage order their
    parameters, so they are named from those stages.
    """
    if not fit_mode.iterative or not progress.last_changes:
        return {}
    active = {spec.name for spec in fit_mode.parameters_for(scattering)}
    names = [
        name
        for stage in fit_mode.stages
        if stage.quantity in ("seebeck", "resistivity")
        for name in stage.parameters
        if name in active
    ]
    if len(names) != len(progress.last_changes):
        return {}
    return dict(zip(names, progress.last_changes, strict=True))


def _points(request: FitRequest) -> dict[Quantity, int]:
    """The points of each quantity the fit was given, for the stages that fit to it."""
    return {
        quantity: int(np.size(measurement.values))
        for quantity, measurement in request.measurements.items()
    }


def _usable_error(error: float) -> bool:
    """Exactly 0, or not finite, means the solver saw no effect of the parameter on the data."""
    return math.isfinite(error) and error > 0


def _is_at_bound(value: float, bound: float) -> bool:
    return math.isfinite(bound) and abs(value - bound) <= AT_BOUND_TOLERANCE * max(abs(bound), 1.0)


def _mass_error(energy: float, energy_error: float) -> float:
    """Carry an error on E = m^(3/2) over to m, so dm = (2/3) E^(-1/3) dE."""
    with np.errstate(all="ignore"):
        return float((2 / 3) * np.abs(energy) ** (-1 / 3) * energy_error)


def _reusing_chemical_potential[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    """Solves each μ(T) once for one curve or fit, and drops the roots when it ends."""

    @functools.wraps(method)
    def within_scope(*args: P.args, **kwargs: P.kwargs) -> R:
        with reuse_chemical_potential():
            return method(*args, **kwargs)

    return within_scope


def _with_parameter_status[**P](method: Callable[P, FitResult]) -> Callable[P, FitResult]:
    """Gives a result the status of each parameter, if its fit has not.

    The legacy fit does that itself, from its stage errors. A verified fit has its unidentified
    parameters, and a failed fit of either kind leaves every fitted parameter not assessed.
    """

    @functools.wraps(method)
    def with_status(*args: P.args, **kwargs: P.kwargs) -> FitResult:
        result = method(*args, **kwargs)
        model, request = args[0], kwargs.get("request", args[1] if len(args) > 1 else None)
        assert isinstance(model, _BandModel) and isinstance(request, FitRequest)
        if result.parameter_status:
            return result
        fit_mode = model._request_mode(request.fit_mode, request.explicit_bands)
        diagnostics = result.diagnostics
        return dataclasses.replace(
            result,
            parameter_status=parameter_statuses(
                fit_mode,
                request.scattering,
                request.start,
                result.parameters,
                status=result.status,
                held=request.held,
                at_bounds=result.at_bounds,
                undetermined=diagnostics.unidentified if diagnostics is not None else (),
                reached=None,
                points=_points(request),
            ),
        )

    return with_status


class _CallbackError(Exception):
    """Carries an error of the caller's callback through the fit, which is not its failure."""

    def __init__(self, original: Exception) -> None:
        super().__init__()
        self.original = original


def _failure_message(error: Exception) -> str:
    """Return fixed text for a failed fit, because solver messages are not written for users."""
    if isinstance(error, _CORE_MATH.NoFiniteChemicalPotentialError):
        return "The fit encountered band parameters with no finite chemical potential."
    if isinstance(error, ChemicalPotentialError):
        return "The chemical-potential balance could not be verified during the fit."
    text = str(error)
    if isinstance(error, ValueError) and "finite lower gap bound" in text:
        return "A gap fit with the Fermi energy held needs a finite lower bound of the gap."
    if isinstance(error, ValueError) and "bounds" in text:
        return "The start values do not fit the bounds."
    if isinstance(error, ValueError) and "contradicts the sign of R_H" in text:
        return "The sign of the start band mass does not match the sign of R_H."
    if isinstance(error, ValueError) and "not finite" in text:
        return "The model gave values that are not finite during the fit."
    if isinstance(error, RuntimeError) and "Optimal parameters not found" in text:
        return "The fit reached its limit of function evaluations."
    return "The fit failed with an internal error."


def _log_failure(error: Exception) -> None:
    """Log where a fit failed, without the error's text, which could hold measured values."""
    frames = traceback.extract_tb(error.__traceback__)
    place = f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "unknown"
    logger.warning("A fit failed with %s at %s", type(error).__name__, place)


def _fitted_names(fit_mode: FitMode, scattering: str | None) -> frozenset[str]:
    """The parameters a fit finds, for its scattering type."""
    return frozenset(
        spec.name for spec in fit_mode.parameters_for(scattering) if spec.role == "fitted"
    )


class _BandModel:
    """What SPB and DPB share: checks, bounds and naming of results."""

    def __init__(self, description: ModelDescription) -> None:
        self._description = description

    def describe(self) -> ModelDescription:
        return self._description

    def _request_mode(self, mode_id: str, explicit: ExplicitBands | None) -> FitMode:
        if explicit is not None:
            if self._description.id != "dpb":
                raise ValueError("Explicit band types require DPB")
            return explicit_dpb_description(explicit.uses_fermi_energy).fit_mode(mode_id)
        return self._description.fit_mode(mode_id)

    def _mode_and_scattering(
        self, fit_mode_id: str, scattering: str | None, explicit: ExplicitBands | None = None
    ) -> tuple[FitMode, str | None]:
        fit_mode = self._request_mode(fit_mode_id, explicit)
        if scattering is None and fit_mode.scattering and not fit_mode.id.endswith("_s"):
            raise ValueError(f"Fit mode {fit_mode_id} needs a scattering type")
        active = fit_mode.parameters_for(scattering)
        specs = {p.name: p for p in fit_mode.parameters}
        specs.update((p.name, p) for p in active)
        # The parameters now hold the overrides of this scattering, so drop them: applied again,
        # they would make `parameters` mean base or merged specs depending on the caller.
        merged = dataclasses.replace(
            fit_mode, parameters=tuple(specs.values()), parameter_overrides=()
        )
        return merged, scattering

    def _check_fit(self, request: FitRequest, fit_mode: FitMode) -> None:
        specs = {spec.name: spec for spec in fit_mode.parameters}
        unknown = [name for name in request.start if name not in specs and name not in ("C", "D")]
        if unknown:
            raise ValueError(f"Fit mode {fit_mode.id} has no parameters {unknown}")
        for name, value in request.start.items():
            if not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"Start value of {name} must be a finite number")
        for name, bounds in request.bounds.items():
            if name in ("C", "D") and request.scattering != "acPhDis":
                continue  # Inert historical inputs for other mechanisms.
            if name not in specs or specs[name].fit_bounds is None:
                raise ValueError(f"Fit mode {fit_mode.id} does not fit a parameter {name}")
            if not bounds.lower < bounds.upper:
                raise ValueError(f"The lower bound of {name} must be below its upper bound")
            if name in ("C", "D") and (
                not math.isfinite(bounds.lower)
                or not math.isfinite(bounds.upper)
                or bounds.lower < 0
            ):
                raise ValueError(
                    f"Mixed scattering bounds for {name} must be finite and nonnegative"
                )
        if request.scattering == "acPhDis":
            for name in ("C", "D"):
                if name in specs and name not in request.start:
                    raise ValueError(f"Mixed scattering needs its crossover ratio {name}")
                if name in specs and request.start[name] < 0:
                    raise ValueError(f"Mixed scattering ratio {name} must be nonnegative")
        fitted = _fitted_names(fit_mode, request.scattering)
        if request.explicit_bands is not None:
            missing = fitted - request.held - request.bounds.keys()
            if missing:
                raise ValueError(f"Choose fit bounds for {sorted(missing)}")
            if any(request.start.get(n, 0.0) <= 0 for n in ("m1", "mass_ratio")):
                raise ValueError("The single-valley masses must be positive")
        not_fitted = sorted(name for name in request.held if name not in fitted)
        if not_fitted:
            raise ValueError(f"Fit mode {fit_mode.id} does not fit parameters {not_fitted}")
        if fitted and fitted <= frozenset(request.held):
            raise ValueError("A fit needs at least one parameter that is not held")
        for quantity in fit_mode.quantities:
            if quantity in request.measurements:
                request.measurements[quantity].check(quantity)

    def _limits(self, request: FitRequest, fit_mode: FitMode, names: Iterable[str]) -> list[Any]:
        """Return [[lower, ...], [upper, ...]], from the request or else the description."""
        specs = {spec.name: spec for spec in fit_mode.parameters}
        chosen: list[Bounds] = []
        for name in names:
            bounds = request.bounds.get(name) or (
                specs[name].fit_bounds if name in specs else Bounds(0, 1e4)
            )
            if bounds is None:
                raise ValueError(f"Parameter {name} has no bounds")
            chosen.append(bounds)
        return [[bounds.lower for bounds in chosen], [bounds.upper for bounds in chosen]]

    def _stage_errors(
        self, fit_mode: FitMode, scattering: str | None, ratio: float, progress: Any
    ) -> dict[str, float]:
        raise NotImplementedError

    def _at_bounds(
        self,
        request: FitRequest,
        fit_mode: FitMode,
        parameters: Mapping[str, float],
        ratio: float,
        stages: Mapping[str, Any],
    ) -> tuple[str, ...]:
        found = []
        for spec in fit_mode.parameters_for(request.scattering):
            bounds = request.bounds.get(spec.name) or spec.fit_bounds
            if spec.role != "fitted" or bounds is None:
                continue
            # A stopped Hall fit never reached its last stage.
            if spec.name in ("m1", "band_mass") and "hall" not in stages:
                continue
            value = parameters[spec.name]
            # With N2/N1 other than 1, the loop fits m_eff / N, and its bounds apply to that (D12).
            if fit_mode.iterative and spec.name == "m_eff":
                value = value / ratio
            if spec.name == "m_eff":
                # Report the same effective branch bounds used by every DPB solver.
                lower, upper = fit_module._dpb_branch_bounds(
                    request.start["m_eff"], ([bounds.lower], [bounds.upper])
                )
                bounds = Bounds(lower[0], upper[0])
            if value <= bounds.lower or value >= bounds.upper:
                found.append(spec.name)
            elif _is_at_bound(value, bounds.lower) or _is_at_bound(value, bounds.upper):
                found.append(spec.name)
            # The SPB Hall fit keeps the mass on the branch of its start, so 0 bounds it too.
            elif (
                spec.name == "band_mass"
                and "hall" in stages
                and bounds.lower < 0 < bounds.upper
                and _is_at_bound(value, 0.0)
            ):
                found.append(spec.name)
        return tuple(found)

    def _ended_fit(
        self,
        request: FitRequest,
        fit_mode: FitMode,
        progress: fit_module.FitProgress,
        parameters: Mapping[str, float],
        status: FitStatus,
    ) -> FitResult:
        ratio = _mode_degeneracy_ratio(request, fit_mode)
        # A held value comes back as sent, not through a solver's units, such as m1 from E^(2/3).
        parameters = dict(parameters) | {name: request.start[name] for name in request.held}
        parameters = {name: value for name, value in parameters.items() if name in request.start}
        errors = self._stage_errors(fit_mode, request.scattering, ratio, progress)
        at_bounds = tuple(
            name
            for name in self._at_bounds(request, fit_mode, parameters, ratio, progress.stage_fits)
            if name not in request.held
        )
        reached = {
            name
            for stage in fit_mode.stages
            if _STAGE_KEYS[stage.quantity] in progress.stage_fits
            for name in stage.parameters
        }
        return FitResult(
            parameters,
            status,
            progress.iterations if fit_mode.iterative else None,
            parameter_errors={
                name: error
                for name, error in errors.items()
                if name not in request.held and _usable_error(error)
            },
            at_bounds=at_bounds,
            known_issues=active_issue_ids(
                fit_mode, request.scattering, parameters, ratio, extrapolated=request.extrapolated
            ),
            held=tuple(sorted(request.held)),
            last_changes=_last_changes(fit_mode, request.scattering, progress),
            parameter_status=parameter_statuses(
                fit_mode,
                request.scattering,
                request.start,
                parameters,
                status=status,
                held=request.held,
                at_bounds=at_bounds,
                # Exactly 0 is a Jacobian column of zeros; not finite is no covariance at all.
                undetermined={name for name, error in errors.items() if error == 0},
                unassessed={name for name, error in errors.items() if not math.isfinite(error)},
                reached=reached,
                points=_points(request),
            ),
        )

    def _progress(self, request: FitRequest, fit_mode: FitMode) -> fit_module.FitProgress:
        """A progress that holds, in each stage, the positions of the parameters held."""
        progress = fit_module.FitProgress()
        if not request.held:
            return progress
        fitted = _fitted_names(fit_mode, request.scattering)
        for stage in fit_mode.stages:
            # A stage's vector holds the parameters of the scattering type, in the stage's order.
            vector = [name for name in stage.parameters if name in fitted]
            positions = frozenset(
                index for index, name in enumerate(vector) if name in request.held
            )
            if positions:
                progress.held[_STAGE_KEYS[stage.quantity]] = positions
        return progress

    def _run_fit(
        self,
        request: FitRequest,
        fit_mode: FitMode,
        function: Callable[..., Any],
        arguments: list[Any],
        keywords: dict[str, Any],
        names: tuple[str, ...],
    ) -> FitResult:
        """Run a single-pass fit, and turn its errors into a status."""
        progress = self._progress(request, fit_mode)
        try:
            fitted = function(*arguments, progress=progress, **keywords)
        except MemoryError:
            raise
        except Exception as error:
            _log_failure(error)
            return FitResult(
                dict(request.start),
                "failed",
                message=_failure_message(error),
                known_issues=disabled_issue_ids(fit_mode),
                held=tuple(sorted(request.held)),
            )
        parameters = dict(request.start) | dict(zip(names, fitted, strict=True))
        return self._ended_fit(request, fit_mode, progress, parameters, "converged")

    def _run_iterative_fit(
        self,
        request: FitRequest,
        fit_mode: FitMode,
        function: Callable[..., Any],
        arguments: list[Any],
        names: tuple[str, ...],
        on_iteration: IterationCallback | None,
    ) -> FitResult:
        """Run a fit with a loop, and turn how it ended into a status."""
        latest = dict(request.start)
        callback_error: Exception | None = None
        progress = self._progress(request, fit_mode)
        if on_iteration is not None:
            callback = on_iteration

            def report(iteration: int, values: list[float]) -> None:
                # A parameter fitted after the loop is not in `values`, so it keeps its start. A
                # held one goes back as sent, not through the loop's units, such as m_eff / N * N.
                latest.update(
                    (name, value)
                    for name, value in zip(names, values, strict=False)
                    if name in request.start
                )
                latest.update({name: request.start[name] for name in request.held})
                try:
                    callback(IterationUpdate(iteration, dict(latest)))
                except FitStopped:
                    raise
                except Exception as error:
                    raise _CallbackError(error) from error

            progress.on_iteration = report
        try:
            fitted = function(*arguments, progress=progress)
        except FitStopped:
            return self._ended_fit(request, fit_mode, progress, latest, "stopped")
        except _CallbackError as error:
            callback_error = error.original
        except MemoryError:
            raise
        except Exception as error:
            _log_failure(error)
            return FitResult(
                dict(request.start),
                "failed",
                progress.iterations,
                _failure_message(error),
                known_issues=disabled_issue_ids(fit_mode),
                held=tuple(sorted(request.held)),
            )
        if callback_error is not None:
            raise callback_error
        status: FitStatus = "iteration_limit" if progress.reached_iteration_limit else "converged"
        result = dict(request.start) | dict(zip(names, fitted, strict=True))
        return self._ended_fit(request, fit_mode, progress, result, status)

    @_reusing_chemical_potential
    def calculate(self, request: CurveRequest) -> CurveResult:
        fit_mode, scattering = self._mode_and_scattering(
            request.fit_mode, request.scattering, request.explicit_bands
        )
        if scattering == "acPhDis" and not fit_mode.id.endswith("_s"):
            declared = {spec.name for spec in fit_mode.parameters}
            for name in ("C", "D"):
                if name not in declared:
                    continue  # SPB has C only.
                if name not in request.parameters:
                    # Elsewhere a missing C or D reads as 0, which would be pure acoustic phonons.
                    raise ValueError(f"Mixed scattering needs its crossover ratio {name}")
                ratio = request.parameters[name]
                if not math.isfinite(ratio) or ratio < 0:
                    raise ValueError(
                        f"Mixed scattering ratio {name} must be finite and nonnegative"
                    )
        if request.kind not in fit_mode.curve_kinds:
            raise ValueError(f"Fit mode {fit_mode.id} has no curve {request.kind}")
        if request.explicit_bands is not None:
            from seeband_core.explicit_transport import explicit_curves

            temperatures = np.linspace(
                request.min_temperature_k, request.max_temperature_k, request.points
            )
            curves = explicit_curves(
                request.explicit_bands,
                fit_mode.id,
                request.parameters,
                temperatures,
                scattering,
                request.band_1_degeneracy,
                request.band_2_degeneracy,
                request.kind,
            )
            issues = active_issue_ids(
                fit_mode,
                scattering,
                request.parameters,
                _degeneracy_ratio(request),
                request.kind,
                extrapolated=request.extrapolated,
                explicit_bands=request.explicit_bands,
            )
            return CurveResult(temperatures, curves, issues)
        if request.kind == "lorenz_number":
            return self._lorenz_number(request, fit_mode, scattering)
        if scattering == "ionized" and request.kind != "carrier_concentration_by_band":
            from seeband_core.transport import ionized_transport

            temperature_k = np.linspace(
                request.min_temperature_k, request.max_temperature_k, request.points
            )
            ratio = _mode_degeneracy_ratio(request, fit_mode)
            predictions = ionized_transport(
                temperature_k,
                request.parameters,
                fit_mode.id,
                ratio,
                band_1_degeneracy=request.band_1_degeneracy,
            )
            keys: tuple[str, ...]
            if request.kind == "measured":
                keys = fit_mode.quantities
                names = _MEASURED_CURVES[: len(keys)]
            else:
                names = _CURVE_NAMES[request.kind]
                keys = tuple(
                    name.removesuffix("_s_per_m")
                    .removesuffix("_v_per_k")
                    .removesuffix("_w_per_m_k")
                    .removesuffix("_k")
                    for name in names
                )
            return CurveResult(
                temperature_k,
                {name: predictions[key] for name, key in zip(names, keys, strict=True)},
                active_issue_ids(
                    fit_mode,
                    scattering,
                    request.parameters,
                    ratio,
                    request.kind,
                    request.extrapolated,
                ),
            )
        function, arguments = self._curve_call(request, fit_mode, scattering)
        result = function(
            request.min_temperature_k, request.max_temperature_k, request.points, *arguments
        )
        temperature_k, *curves = result
        names = (
            _MEASURED_CURVES[: len(curves)]
            if request.kind == "measured"
            else _CURVE_NAMES[request.kind]
        )
        ratio = _mode_degeneracy_ratio(request, fit_mode)
        return CurveResult(
            temperature_k,
            dict(zip(names, curves, strict=True)),
            active_issue_ids(
                fit_mode, scattering, request.parameters, ratio, request.kind, request.extrapolated
            ),
        )

    def _lorenz_number(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> CurveResult:
        """Calculate absolute L in W Ω/K² from transport moments.

        DPB includes the conductivity-weighted band moments and the bipolar term.
        The shared conductivity amplitude cancels; an explicit zero keeps the
        historical undefined effective L, while each band's L remains defined.
        """
        temperature_k = np.linspace(
            request.min_temperature_k, request.max_temperature_k, request.points
        )
        parameters = request.parameters
        ratio = _mode_degeneracy_ratio(request, fit_mode)
        bands: dict[str, np.ndarray] = {}
        if scattering == "ionized":
            from seeband_core.transport import ionized_transport

            # Only normalized moments are needed. Do not let the absolute
            # amplitude overflow or underflow the auxiliary transport outputs.
            predictions = ionized_transport(
                temperature_k, dict(parameters) | {"A": 1.0}, fit_mode.id, ratio
            )
            effective = predictions["lorenz_number"]
            if fit_mode.degeneracy is not None:
                bands = {
                    LORENZ_BAND_CURVES[0]: predictions["lorenz_band_1"],
                    LORENZ_BAND_CURVES[1]: predictions["lorenz_band_2"],
                }
        elif scattering not in _MOMENT_SCATTERING:
            # Each mechanism needs its own band weight before L may come from the moments.
            raise ValueError(f"No Lorenz moments for scattering {scattering!r}")
        elif fit_mode.degeneracy is not None:
            relative: float | np.ndarray = _value(parameters, "G" if scattering == "dis" else "B")
            if scattering == "acPhDis":
                # As in the κ_e and σ of mixed scattering: band 2's weight varies with T.
                relative = (
                    relative
                    * (300.0 * _value(parameters, "C") + temperature_k)
                    / (300.0 * _value(parameters, "D") + temperature_k)
                )
            effective, band1, band2 = _CORE_MATH.dpb_lorenz_moments(
                temperature_k,
                _value(parameters, "m_eff") / ratio,
                _value(parameters, "band_gap"),
                _value(parameters, "fermi_energy"),
                ratio,
                relative,
            )
            bands = dict(zip(LORENZ_BAND_CURVES, (band1, band2), strict=True))
        else:
            # One band: its L does not depend on the amplitude, nor on C in acPhDis, as both
            # mechanisms there share the energy exponent.
            effective = _CORE_MATH.spb_lorNum_vs_temp(
                temperature_k, _value(parameters, "fermi_energy"), _value(parameters, "band_mass")
            )
        amplitude = parameters.get(_amplitude_name(scattering), 1.0)
        if not np.isfinite(amplitude) or amplitude == 0.0:
            # σ and κ_e are zero, infinite or undefined, so their ratio is too; each band's L stays.
            effective = np.full_like(effective, np.nan)
        curves = {LORENZ_CURVE: effective} | bands
        # L is κ_e/(σT), so it carries the known issues of both as well as its own.
        issues = tuple(
            dict.fromkeys(
                issue
                for kind in (request.kind, "thermal_conductivity", "electrical_conductivity")
                for issue in active_issue_ids(
                    fit_mode, scattering, parameters, ratio, kind, request.extrapolated
                )
            )
        )
        return CurveResult(temperature_k, curves, issues)

    def band_diagram(self, request: BandDiagramRequest) -> BandDiagramResult:
        """Return the local parabolic bands and constant Fermi energy."""
        if request.explicit_bands is not None:
            from seeband_core.explicit_transport import explicit_diagram

            self._request_mode(request.fit_mode, request.explicit_bands)
            return explicit_diagram(
                request.explicit_bands,
                request.parameters,
                request.band_1_degeneracy,
                request.band_2_degeneracy,
            )
        fit_mode = self.describe().fit_mode(request.fit_mode)
        wavevector_nm_inv: np.ndarray | None = None
        curves: dict[str, np.ndarray] = {}
        # A mass very close to 0 can put the energies outside the range of a float.
        with np.errstate(over="ignore"):
            for name, mass, energy in self._diagram_bands(request, fit_mode):
                wavevector_nm_inv, curves[name] = parabolic_band(
                    *_DIAGRAM_K_RANGE_NM_INV, _DIAGRAM_POINTS, mass, energy
                )
        assert wavevector_nm_inv is not None
        curves["fermi_energy_k"] = np.full_like(
            wavevector_nm_inv, _value(request.parameters, "fermi_energy")
        )
        # Without Hall data no mode sets a mass's size, so band 1's is taken as mₑ. With them, the
        # curvature follows the current mass, which the data set only once a fit has run.
        reference_mass_assumed = "hall" not in fit_mode.quantities
        return BandDiagramResult(
            wavevector_nm_inv,
            curves,
            band_diagram_issue_ids(fit_mode),
            reference_mass_assumed=reference_mass_assumed,
        )

    def _diagram_bands(
        self, request: BandDiagramRequest, fit_mode: FitMode
    ) -> list[tuple[str, float, float]]:
        """Each curve name, signed single-valley mass in m_e, and edge energy in K."""
        raise NotImplementedError

    def _curve_call(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> tuple[Callable[..., Any], list[Any]]:
        raise NotImplementedError


class SpbModel(_BandModel):
    def __init__(self) -> None:
        super().__init__(load_desktop_descriptions()["spb"])

    def _diagram_bands(
        self, request: BandDiagramRequest, fit_mode: FitMode
    ) -> list[tuple[str, float, float]]:
        """The band's signed mass. Without Hall data only its sign is set by the data, as S does
        not depend on its size and ρ's prefactor absorbs it, so the curvature takes |m| = mₑ."""
        mass = _value(request.parameters, "band_mass")
        if "hall" not in fit_mode.quantities:
            mass = float(np.sign(mass))
        return [("band_1_energy_k", mass, 0.0)]

    def _stage_errors(
        self, fit_mode: FitMode, scattering: str | None, ratio: float, progress: Any
    ) -> dict[str, float]:
        stages = progress.stage_fits
        errors: dict[str, float] = {}
        if "see" in stages:
            errors |= _named_errors(["fermi_energy"], _standard_errors(stages["see"][1]))
        if "res" in stages:
            res = _standard_errors(stages["res"][1])
            if scattering == "dis":
                errors |= _named_errors(["F"], res)
            elif scattering == "acPh":
                errors |= _named_errors(["A"], res)
            else:
                errors |= _named_errors(["A", "C"], [res[0], res[1] / 300.0])
        if "hall" in stages:
            energy, covariance = stages["hall"]
            error = _standard_errors(covariance)[0]
            errors |= _named_errors(["band_mass"], [_mass_error(energy[0], error)])
        return errors

    def _curve_call(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> tuple[Callable[..., Any], list[Any]]:
        parameters = request.parameters
        band = [_value(parameters, "band_mass"), _value(parameters, "fermi_energy")]
        if request.kind == "chemical_potential":
            return _CORE.spb_chemPot_calc, band
        if request.kind == "measured" and fit_mode.id == "spb_s":
            return _CORE.spb_see_calc, band
        function = {
            "electrical_conductivity": _CORE.spb_elecCond_calc,
            "thermal_conductivity": _CORE.spb_thermCond_calc,
            "measured": (
                _CORE.spb_see_res_calc
                if fit_mode.id == "spb_s_rho"
                else _CORE.spb_see_res_hall_calc
            ),
        }[str(request.kind)]
        return function, [*band, _values(parameters, _SPB_SCATTERING), scattering]

    @_with_parameter_status
    @_reusing_chemical_potential
    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        fit_mode, scattering = self._mode_and_scattering(
            request.fit_mode, request.scattering, request.explicit_bands
        )
        self._check_fit(request, fit_mode)
        if request.algorithm == "verified-sequential-v2":
            from seeband_core.verified_fit import fit_verified

            _values(request.start, (spec.name for spec in fit_mode.parameters))
            _measurement_arrays(request.measurements, fit_mode.quantities)
            if fit_mode.degeneracy is not None:
                _degeneracy_ratio(request)
            return fit_verified(request, fit_mode, on_iteration)
        if scattering == "ionized":
            raise ValueError("Ionized scattering requires verified-sequential-v2")
        if request.algorithm != "legacy-sequential-v1":
            raise ValueError("Unknown fitting algorithm")
        start = request.start
        data = _measurement_arrays(request.measurements, fit_mode.quantities)
        fermi: list[Any] = [
            [_value(start, "fermi_energy")],
            self._limits(request, fit_mode, ["fermi_energy"]),
        ]
        if fit_mode.id == "spb_s":
            arguments = [*data, _value(start, "band_mass"), *fermi]
            return self._run_fit(
                request, fit_mode, _CORE.spb_see_fit, arguments, {}, ("fermi_energy",)
            )
        scattering_start: list[Any] = [
            _values(start, _SPB_SCATTERING),
            self._limits(request, fit_mode, _SPB_SCATTERING),
        ]
        if fit_mode.id == "spb_s_rho":
            arguments = [*data, _value(start, "band_mass"), *fermi, *scattering_start]
            return self._run_fit(
                request,
                fit_mode,
                _CORE.spb_see_res_fit,
                arguments,
                {"scatter_type": scattering},
                ("fermi_energy", *_SPB_SCATTERING),
            )
        arguments = [
            *data,
            *fermi,
            *scattering_start,
            [_value(start, "band_mass")],
            self._limits(request, fit_mode, ["band_mass"]),
            scattering,
        ]
        return self._run_fit(
            request,
            fit_mode,
            _CORE.spb_see_res_hall_fit,
            arguments,
            {},
            ("fermi_energy", *_SPB_SCATTERING, "band_mass"),
        )


class DpbModel(_BandModel):
    def __init__(self) -> None:
        super().__init__(load_desktop_descriptions()["dpb"])

    def _diagram_bands(
        self, request: BandDiagramRequest, fit_mode: FitMode
    ) -> list[tuple[str, float, float]]:
        """Convert the Hall density-of-states mass to a signed single-valley mass."""
        mass_1 = -1.0
        if "hall" in fit_mode.quantities:
            mass_1 = -abs(_value(request.parameters, "m1")) / request.band_1_degeneracy ** (2 / 3)
        mass_2 = _value(request.parameters, "m_eff") * abs(mass_1)
        return [
            ("band_1_energy_k", mass_1, 0.0),
            ("band_2_energy_k", mass_2, _value(request.parameters, "band_gap")),
        ]

    def _stage_errors(
        self, fit_mode: FitMode, scattering: str | None, ratio: float, progress: Any
    ) -> dict[str, float]:
        stages = progress.stage_fits
        errors: dict[str, float] = {}
        if "see" in stages:
            see = _standard_errors(stages["see"][1])
            # The loop returns m_eff multiplied by N (D12).
            scale = ratio if fit_mode.iterative else 1.0
            errors |= _named_errors(_DPB_BANDS, [see[0] * scale, see[1], see[2]])
        if "res" in stages:
            res = _standard_errors(stages["res"][1])
            if scattering == "dis":
                errors |= _named_errors(["F", "G"], res)
            elif scattering == "acPh":
                errors |= _named_errors(["A", "B"], res)
            else:
                # The fit works on C and D multiplied by 300.
                errors |= _named_errors(
                    ["A", "B", "C", "D"], [res[0], res[1], res[2] / 300.0, res[3] / 300.0]
                )
        if "hall" in stages:
            energy, covariance = stages["hall"]
            error = _standard_errors(covariance)[0]
            errors |= _named_errors(["m1"], [_mass_error(energy[0], error)])
        return errors

    def _curve_call(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> tuple[Callable[..., Any], list[Any]]:
        parameters = request.parameters
        degeneracy = _degeneracy_ratio(request)
        bands = _values(parameters, _DPB_BANDS)
        kind = request.kind
        if kind == "chemical_potential":
            return _CORE.dpb_chemPot_calc, [bands, degeneracy]
        if kind == "carrier_concentration_by_band":
            if fit_mode.id == "dpb_s_rho_rh":
                m1 = _value(parameters, "m1")
                return _CORE.dpb_ind_carCon_calc_m1, [
                    bands,
                    degeneracy,
                    m1,
                    request.band_1_degeneracy,
                ]
            return _CORE.dpb_ind_carCon_calc, [bands, degeneracy]
        if fit_mode.id == "dpb_s":
            function = _CORE.dpb_see_calc if kind == "measured" else _CORE.dpb_ind_see_seeOnly_calc
            return function, [bands, degeneracy]
        scattering_values = _values(parameters, _DPB_SCATTERING)
        if kind == "measured" and fit_mode.id == "dpb_s_rho_rh":
            m1 = _value(parameters, "m1")
            return _CORE.dpb_see_res_hall_calc, [
                bands,
                scattering_values,
                m1,
                degeneracy,
                scattering,
                request.band_1_degeneracy,
            ]
        function = {
            "measured": _CORE.dpb_see_res_calc,
            "seebeck": _CORE.dpb_see_with_scatter_calc,
            "seebeck_by_band": _CORE.dpb_ind_see_calc,
            "electrical_conductivity": _CORE.dpb_elecCond_calc,
            "electrical_conductivity_by_band": _CORE.dpb_ind_elecCond_calc,
            "thermal_conductivity": _CORE.dpb_thermCond_calc,
        }[str(kind)]
        return function, [bands, scattering_values, degeneracy, scattering]

    @_with_parameter_status
    @_reusing_chemical_potential
    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        fit_mode, scattering = self._mode_and_scattering(
            request.fit_mode, request.scattering, request.explicit_bands
        )
        if (
            request.explicit_bands is not None
            and scattering == "ionized"
            and fit_mode.id == "dpb_s"
        ):
            request = dataclasses.replace(request, start={"B": 1.0} | dict(request.start))
        if request.explicit_bands is not None and request.algorithm != "verified-sequential-v2":
            raise ValueError("Explicit bands require the verified fitting algorithm")
        self._check_fit(request, fit_mode)
        if request.algorithm == "verified-sequential-v2":
            from seeband_core.verified_fit import fit_verified

            _values(request.start, (spec.name for spec in fit_mode.parameters))
            _measurement_arrays(request.measurements, fit_mode.quantities)
            if fit_mode.degeneracy is not None:
                _degeneracy_ratio(request)
            if request.explicit_bands is not None:
                from seeband_core.explicit_transport import reuse_explicit_potentials

                with reuse_explicit_potentials():
                    return fit_verified(request, fit_mode, on_iteration)
            return fit_verified(request, fit_mode, on_iteration)
        if scattering == "ionized":
            raise ValueError("Ionized scattering requires verified-sequential-v2")
        if request.algorithm != "legacy-sequential-v1":
            raise ValueError("Unknown fitting algorithm")
        start = request.start
        data = _measurement_arrays(request.measurements, fit_mode.quantities)
        degeneracy = _degeneracy_ratio(request)
        bands: list[Any] = [
            _values(start, _DPB_BANDS),
            self._limits(request, fit_mode, _DPB_BANDS),
        ]
        if fit_mode.id == "dpb_s":
            arguments = [*data, *bands, degeneracy]
            return self._run_fit(request, fit_mode, _CORE.dpb_see_fit, arguments, {}, _DPB_BANDS)
        if "m_eff" in request.held:
            # The loop fits m_eff / N and returns it times N (D12), so a held m_eff goes in divided,
            # and the bands keep the mass sent.
            bands[0][0] = bands[0][0] / degeneracy
        scattering_start: list[Any] = [
            _values(start, _DPB_SCATTERING),
            self._limits(request, fit_mode, _DPB_SCATTERING),
        ]
        loop = [degeneracy, scattering, fit_mode.threshold, fit_mode.max_iterations]
        names = (*_DPB_BANDS, *_DPB_SCATTERING)
        if fit_mode.id == "dpb_s_rho":
            return self._run_iterative_fit(
                request,
                fit_mode,
                _CORE.dpb_see_res_fit,
                [*data, *bands, *scattering_start, *loop],
                names,
                on_iteration,
            )
        arguments = [
            *data,
            *bands,
            *scattering_start,
            _value(start, "m1"),
            self._limits(request, fit_mode, ["m1"]),
            *loop,
        ]
        return self._run_iterative_fit(
            request,
            fit_mode,
            functools.partial(
                _CORE.dpb_see_res_hall_fit, band_1_degeneracy=request.band_1_degeneracy
            ),
            arguments,
            (*names, "m1"),
            on_iteration,
        )
