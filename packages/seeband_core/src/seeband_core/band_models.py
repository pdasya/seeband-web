"""SPB and DPB behind the model interface, with the numbers of the ported calculations.

Everything here is in core units, so nothing here converts a scale. Results keep the order of the
calculations they come from.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import numpy as np

from seeband_core import fit_module
from seeband_core.model_descriptions import load_desktop_descriptions
from seeband_core.model_interface import (
    Bounds,
    CurveKind,
    CurveRequest,
    CurveResult,
    FitMode,
    FitRequest,
    FitResult,
    IterationCallback,
    Measurement,
    ModelDescription,
    Quantity,
)

# Any, because calls here spread lists of mixed arguments that mypy cannot match to a signature.
_CORE: Any = fit_module.PB_fit()
_SPB_SCATTERING = ("A", "C", "F")
_DPB_BANDS = ("m_eff", "band_gap", "fermi_energy")
_DPB_SCATTERING = ("A", "B", "C", "D", "F", "G")
_MEASURED_CURVES = ("seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c")
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


def _values(parameters: Mapping[str, float], names: Iterable[str]) -> list[float]:
    names = list(names)
    missing = [name for name in names if name not in parameters]
    if missing:
        raise ValueError(f"Missing parameters: {missing}")
    return [parameters[name] for name in names]


def _value(parameters: Mapping[str, float], name: str) -> float:
    return _values(parameters, [name])[0]


def _degeneracy_ratio(request: CurveRequest | FitRequest) -> float:
    if request.band_1_degeneracy <= 0 or request.band_2_degeneracy <= 0:
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
        for name in request.bounds:
            if name not in specs or specs[name].fit_bounds is None:
                raise ValueError(f"Fit mode {fit_mode.id} does not fit a parameter {name}")

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
        return CurveResult(temperature_k, dict(zip(names, curves, strict=True)))

    def _curve_call(
        self, request: CurveRequest, fit_mode: FitMode, scattering: str | None
    ) -> tuple[Callable[..., Any], list[Any]]:
        raise NotImplementedError


class SpbModel(_BandModel):
    def __init__(self) -> None:
        super().__init__(load_desktop_descriptions()["spb"])

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
        fermi: tuple[Any, Any] = (
            [_value(start, "fermi_energy")],
            self._limits(request, fit_mode, ["fermi_energy"]),
        )
        result = dict(start)
        if fit_mode.id == "spb_s":
            fitted = _CORE.spb_see_fit(*data, _value(start, "band_mass"), *fermi)
            names: tuple[str, ...] = ("fermi_energy",)
        else:
            scattering_start: tuple[Any, Any] = (
                _values(start, _SPB_SCATTERING),
                self._limits(request, fit_mode, _SPB_SCATTERING),
            )
            if fit_mode.id == "spb_s_rho":
                fitted = _CORE.spb_see_res_fit(
                    *data,
                    _value(start, "band_mass"),
                    *fermi,
                    *scattering_start,
                    scatter_type=scattering,
                )
                names = ("fermi_energy", *_SPB_SCATTERING)
            else:
                fitted = _CORE.spb_see_res_hall_fit(
                    *data,
                    *fermi,
                    *scattering_start,
                    [_value(start, "band_mass")],
                    self._limits(request, fit_mode, ["band_mass"]),
                    scattering,
                )
                names = ("fermi_energy", *_SPB_SCATTERING, "band_mass")
        result.update(zip(names, fitted, strict=True))
        return FitResult(result)


class DpbModel(_BandModel):
    def __init__(self) -> None:
        super().__init__(load_desktop_descriptions()["dpb"])

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
        bands: tuple[Any, Any] = (
            _values(start, _DPB_BANDS),
            self._limits(request, fit_mode, _DPB_BANDS),
        )
        result = dict(start)
        if fit_mode.id == "dpb_s":
            fitted = _CORE.dpb_see_fit(*data, *bands, degeneracy)
            names: tuple[str, ...] = _DPB_BANDS
        else:
            scattering_start: tuple[Any, Any] = (
                _values(start, _DPB_SCATTERING),
                self._limits(request, fit_mode, _DPB_SCATTERING),
            )
            if fit_mode.id == "dpb_s_rho":
                fitted = _CORE.dpb_see_res_fit(
                    *data,
                    *bands,
                    *scattering_start,
                    degeneracy,
                    scattering,
                    fit_mode.threshold,
                    fit_mode.max_iterations,
                )
                names = (*_DPB_BANDS, *_DPB_SCATTERING)
            else:
                fitted = _CORE.dpb_see_res_hall_fit(
                    *data,
                    *bands,
                    *scattering_start,
                    _value(start, "m1"),
                    self._limits(request, fit_mode, ["m1"]),
                    degeneracy,
                    scattering,
                    fit_mode.threshold,
                    fit_mode.max_iterations,
                )
                names = (*_DPB_BANDS, *_DPB_SCATTERING, "m1")
        result.update(zip(names, fitted, strict=True))
        return FitResult(result)
