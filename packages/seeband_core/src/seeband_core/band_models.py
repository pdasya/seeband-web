"""SPB and DPB behind the model interface, with the numbers of the ported calculations.

Everything here is in core units, so nothing here converts a scale. Results keep the order of the
calculations they come from.
"""

import logging
import math
import traceback
from collections.abc import Callable, Iterable, Mapping
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np

from seeband_core import fit_module
from seeband_core.known_issues import (
    active_issue_ids,
    band_diagram_issue_ids,
    disabled_issue_ids,
)
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
    load_desktop_descriptions,
)
from seeband_core.model_interface import (
    BandDiagramRequest,
    BandDiagramResult,
    Bounds,
    CurveKind,
    CurveRequest,
    CurveResult,
    FitMode,
    FitRequest,
    FitResult,
    FitStatus,
    FitStopped,
    IterationCallback,
    IterationUpdate,
    Measurement,
    ModelDescription,
    ParameterSpec,
    Quantity,
)
from seeband_core.model_scales import core_to_display

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


def parabolic_band(
    min_wavevector: float, max_wavevector: float, points: int, mass: float, energy: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return the band diagram, which depends on no model state. P17 reviews its formula."""
    wavevector, band_energy = _CORE.get_parabolic_band(
        min_wavevector, max_wavevector, points, mass, energy
    )
    return wavevector, band_energy


# As the desktop redraws its sketch: this range of k, this many points, and for E_F a band so heavy
# that it lies flat.
_DIAGRAM_K_RANGE = (-40, 40)
_DIAGRAM_POINTS = 100
_FLAT_MASS = 100000000


def _values(parameters: Mapping[str, float], names: Iterable[str]) -> list[float]:
    names = list(names)
    missing = [name for name in names if name not in parameters]
    if missing:
        raise ValueError(f"Missing parameters: {missing}")
    return [parameters[name] for name in names]


def _value(parameters: Mapping[str, float], name: str) -> float:
    return _values(parameters, [name])[0]


def _degeneracy_ratio(request: CurveRequest | FitRequest) -> float:
    for degeneracy in (request.band_1_degeneracy, request.band_2_degeneracy):
        if not 0 < degeneracy < math.inf:
            raise ValueError("Band degeneracies must be positive")
    return request.band_2_degeneracy / request.band_1_degeneracy


def _measurement_arrays(
    measurements: Mapping[Quantity, Measurement], quantities: Iterable[Quantity]
) -> list[Any]:
    arrays: list[Any] = []
    for quantity in quantities:
        if quantity not in measurements:
            raise ValueError(f"Missing measurement: {quantity}")
        arrays += [measurements[quantity].temperature_k, measurements[quantity].values]
    return arrays


def _standard_errors(covariance: np.ndarray) -> list[float]:
    """Return the standard error of each value, with NaN where the covariance gives none."""
    with np.errstate(invalid="ignore"):
        errors = np.sqrt(np.diag(covariance))
    return [float(error) if np.isfinite(error) else math.nan for error in errors]


def _named_errors(names: Iterable[str], errors: Iterable[float]) -> dict[str, float]:
    """Keep usable errors. Exactly 0 means the solver saw no effect of the parameter on the data."""
    return {
        name: error
        for name, error in zip(names, errors, strict=True)
        if math.isfinite(error) and error > 0
    }


def _is_at_bound(value: float, bound: float) -> bool:
    return math.isfinite(bound) and abs(value - bound) <= AT_BOUND_TOLERANCE * max(abs(bound), 1.0)


def _mass_error(energy: float, energy_error: float) -> float:
    """Carry an error on E = m^(3/2) over to m, so dm = (2/3) E^(-1/3) dE."""
    with np.errstate(all="ignore"):
        return float((2 / 3) * np.abs(energy) ** (-1 / 3) * energy_error)


class _CallbackError(Exception):
    """Carries an error of the caller's callback through the fit, which is not its failure."""

    def __init__(self, original: Exception) -> None:
        super().__init__()
        self.original = original


def _failure_message(error: Exception) -> str:
    """Return fixed text for a failed fit, because solver messages are not written for users."""
    text = str(error)
    if isinstance(error, ValueError) and "bounds" in text:
        return "The start values do not fit the bounds."
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

    def _mode_and_scattering(
        self, fit_mode_id: str, scattering: str | None
    ) -> tuple[FitMode, str | None]:
        fit_mode = self._description.fit_mode(fit_mode_id)
        if scattering is None and fit_mode.scattering:
            raise ValueError(f"Fit mode {fit_mode_id} needs a scattering type")
        fit_mode.parameters_for(scattering)
        return fit_mode, scattering

    def _check_fit(self, request: FitRequest, fit_mode: FitMode) -> None:
        specs = {spec.name: spec for spec in fit_mode.parameters}
        unknown = [name for name in request.start if name not in specs]
        if unknown:
            raise ValueError(f"Fit mode {fit_mode.id} has no parameters {unknown}")
        for name, value in request.start.items():
            if not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"Start value of {name} must be a finite number")
        for name, bounds in request.bounds.items():
            if name not in specs or specs[name].fit_bounds is None:
                raise ValueError(f"Fit mode {fit_mode.id} does not fit a parameter {name}")
            if not bounds.lower < bounds.upper:
                raise ValueError(f"The lower bound of {name} must be below its upper bound")
        fitted = _fitted_names(fit_mode, request.scattering)
        not_fitted = sorted(name for name in request.held if name not in fitted)
        if not_fitted:
            raise ValueError(f"Fit mode {fit_mode.id} does not fit parameters {not_fitted}")
        if fitted and fitted <= request.held:
            raise ValueError("A fit needs at least one parameter that is not held")
        for quantity in fit_mode.quantities:
            if quantity in request.measurements:
                request.measurements[quantity].check(quantity)

    def _limits(self, request: FitRequest, fit_mode: FitMode, names: Iterable[str]) -> list[Any]:
        """Return [[lower, ...], [upper, ...]], from the request or else the description."""
        specs = {spec.name: spec for spec in fit_mode.parameters}
        chosen: list[Bounds] = []
        for name in names:
            bounds = request.bounds.get(name) or specs[name].fit_bounds
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
            # SPB S + rho + R_H returns C still multiplied by 300 (D6).
            if fit_mode.id == "spb_s_rho_rh" and spec.name == "C":
                value = value / 300.0
            if value <= bounds.lower or value >= bounds.upper:
                found.append(spec.name)
            elif _is_at_bound(value, bounds.lower) or _is_at_bound(value, bounds.upper):
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
        ratio = _degeneracy_ratio(request) if fit_mode.degeneracy is not None else 1.0
        # A held value comes back as sent, not through a solver's units, such as m1 from E^(2/3).
        parameters = dict(parameters) | {name: request.start[name] for name in request.held}
        errors = self._stage_errors(fit_mode, request.scattering, ratio, progress)
        at_bounds = self._at_bounds(request, fit_mode, parameters, ratio, progress.stage_fits)
        return FitResult(
            parameters,
            status,
            progress.iterations if fit_mode.iterative else None,
            parameter_errors={
                name: error for name, error in errors.items() if name not in request.held
            },
            at_bounds=tuple(name for name in at_bounds if name not in request.held),
            known_issues=active_issue_ids(
                fit_mode, request.scattering, parameters, ratio, extrapolated=request.extrapolated
            ),
            held=tuple(sorted(request.held)),
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
                # A parameter fitted after the loop is not in `values`, so it keeps its start.
                latest.update(zip(names, values, strict=False))
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

    def calculate(self, request: CurveRequest) -> CurveResult:
        fit_mode, scattering = self._mode_and_scattering(request.fit_mode, request.scattering)
        if request.kind not in fit_mode.curve_kinds:
            raise ValueError(f"Fit mode {fit_mode.id} has no curve {request.kind}")
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
        ratio = _degeneracy_ratio(request) if fit_mode.degeneracy is not None else 1.0
        return CurveResult(
            temperature_k,
            dict(zip(names, curves, strict=True)),
            active_issue_ids(
                fit_mode, scattering, request.parameters, ratio, request.kind, request.extrapolated
            ),
        )

    def band_diagram(self, request: BandDiagramRequest) -> BandDiagramResult:
        """Return the desktop's sketch of the bands. It enters no fit or curve."""
        fit_mode = self.describe().fit_mode(request.fit_mode)
        specs = {spec.name: spec for spec in fit_mode.parameters}
        bands = [
            *self._diagram_bands(request, specs),
            ("fermi_energy_k", _FLAT_MASS, _value(request.parameters, "fermi_energy")),
        ]
        wavevector: np.ndarray | None = None
        curves: dict[str, np.ndarray] = {}
        # A mass of 0, which the controls allow, has no finite band, and a tiny one overflows.
        with np.errstate(all="ignore"):
            for name, mass, energy in bands:
                wavevector, curves[name] = parabolic_band(
                    *_DIAGRAM_K_RANGE, _DIAGRAM_POINTS, mass, energy
                )
        assert wavevector is not None
        return BandDiagramResult(wavevector, curves, band_diagram_issue_ids(fit_mode))

    def _diagram_bands(
        self, request: BandDiagramRequest, specs: Mapping[str, ParameterSpec]
    ) -> list[tuple[str, float, float]]:
        """Each band as its curve's name, its mass as a user sees it, and its energy."""
        raise NotImplementedError

    def _curve_call(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> tuple[Callable[..., Any], list[Any]]:
        raise NotImplementedError


class SpbModel(_BandModel):
    def __init__(self) -> None:
        super().__init__(load_desktop_descriptions()["spb"])

    def _diagram_bands(
        self, request: BandDiagramRequest, specs: Mapping[str, ParameterSpec]
    ) -> list[tuple[str, float, float]]:
        mass = core_to_display(specs["band_mass"], _value(request.parameters, "band_mass"))
        return [("band_1_energy_k", mass, 0)]

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
                # S + rho returns C divided by 300, and S + rho + R_H does not (D6).
                divisor = 300.0 if fit_mode.id == "spb_s_rho" else 1.0
                errors |= _named_errors(["A", "C"], [res[0], res[1] / divisor])
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

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        fit_mode, scattering = self._mode_and_scattering(request.fit_mode, request.scattering)
        self._check_fit(request, fit_mode)
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
        self, request: BandDiagramRequest, specs: Mapping[str, ParameterSpec]
    ) -> list[tuple[str, float, float]]:
        m_eff = core_to_display(specs["m_eff"], _value(request.parameters, "m_eff"))
        ratio = request.band_1_degeneracy / request.band_2_degeneracy
        return [
            # The desktop draws band 1 with this mass, whatever the parameters are.
            ("band_1_energy_k", -1, 0),
            ("band_2_energy_k", m_eff / ratio, _value(request.parameters, "band_gap")),
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
                return _CORE.dpb_ind_carCon_calc_m1, [bands, degeneracy, m1]
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

    def fit(self, request: FitRequest, on_iteration: IterationCallback | None = None) -> FitResult:
        fit_mode, scattering = self._mode_and_scattering(request.fit_mode, request.scattering)
        self._check_fit(request, fit_mode)
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
            request, fit_mode, _CORE.dpb_see_res_hall_fit, arguments, (*names, "m1"), on_iteration
        )
