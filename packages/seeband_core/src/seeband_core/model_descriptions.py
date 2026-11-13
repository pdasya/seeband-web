"""Build the SPB and DPB descriptions from the table of desktop modes."""

import json
from importlib import resources
from typing import Any

from seeband_core.known_issues import issues_for_mode
from seeband_core.model_interface import (
    Bounds,
    CurveKind,
    Degeneracy,
    FitMode,
    FitStage,
    ModelDescription,
    ParameterSpec,
    Quantity,
    UnavailableCurve,
    ValueRange,
)
from seeband_core.model_scales import (
    BOLTZMANN_EV_PER_K,
    ENERGY_DISPLAY_STEP_EV,
    ENERGY_DISPLAY_UNIT,
)

MODEL_NAMES = {"SPB": "Single parabolic band", "DPB": "Double parabolic band"}
MODELS_WITH_INITIAL_GUESS = ("SPB", "DPB")
FIT_MODE_QUANTITIES: dict[str, tuple[Quantity, ...]] = {
    "S": ("seebeck",),
    "S+rho": ("seebeck", "resistivity"),
    "S+rho+R_H": ("seebeck", "resistivity", "hall"),
}
# The curves of each mode: the main curve, and those of the desktop's additional graphs windows.
_SPB_FIT_CURVES: tuple[CurveKind, ...] = (
    "measured",
    "chemical_potential",
    "electrical_conductivity",
    "thermal_conductivity",
)
_DPB_FIT_CURVES: tuple[CurveKind, ...] = (
    "measured",
    "seebeck",
    "seebeck_by_band",
    "chemical_potential",
    "electrical_conductivity",
    "electrical_conductivity_by_band",
    "thermal_conductivity",
    "carrier_concentration_by_band",
)
CURVE_KINDS: dict[str, tuple[CurveKind, ...]] = {
    "spb_s": ("measured", "chemical_potential"),
    "spb_s_rho": _SPB_FIT_CURVES,
    "spb_s_rho_rh": _SPB_FIT_CURVES,
    "dpb_s": ("measured", "seebeck_by_band", "chemical_potential", "carrier_concentration_by_band"),
    "dpb_s_rho": _DPB_FIT_CURVES,
    "dpb_s_rho_rh": _DPB_FIT_CURVES,
}
_Unavailable = tuple[tuple[CurveKind, str], ...]
_NEEDS_RESISTIVITY: _Unavailable = (
    ("electrical_conductivity", "needs_resistivity"),
    ("thermal_conductivity", "needs_resistivity"),
)
_SPB_UNAVAILABLE: _Unavailable = (
    ("seebeck", "same_as_measured"),
    ("seebeck_by_band", "single_band"),
    ("electrical_conductivity_by_band", "single_band"),
    ("carrier_concentration_by_band", "not_on_desktop"),
)
# Why a mode lacks a kind of curve, as a code that a client shows through i18n.
UNAVAILABLE_CURVES: dict[str, _Unavailable] = {
    "spb_s": (*_SPB_UNAVAILABLE, *_NEEDS_RESISTIVITY),
    "spb_s_rho": _SPB_UNAVAILABLE,
    "spb_s_rho_rh": _SPB_UNAVAILABLE,
    "dpb_s": (
        ("seebeck", "same_as_measured"),
        *_NEEDS_RESISTIVITY,
        ("electrical_conductivity_by_band", "needs_resistivity"),
    ),
    "dpb_s_rho": (),
    "dpb_s_rho_rh": (),
}
# The parameters of the solver runs, which `band_models` passes in this order.
SPB_SCATTERING = ("A", "C", "F")
DPB_BANDS = ("m_eff", "band_gap", "fermi_energy")
DPB_SCATTERING = ("A", "B", "C", "D", "F", "G")
# The solver runs of each mode, in the order of `fit_module`: an SPB fit runs each once, and a DPB
# fit with ρ repeats its S and ρ runs until they settle, and fits m1 to R_H after them.
STAGES: dict[str, tuple[FitStage, ...]] = {
    "spb_s": (FitStage("seebeck", ("fermi_energy",)),),
    "spb_s_rho": (
        FitStage("seebeck", ("fermi_energy",)),
        FitStage("resistivity", SPB_SCATTERING),
    ),
    "spb_s_rho_rh": (
        FitStage("seebeck", ("fermi_energy",)),
        FitStage("resistivity", SPB_SCATTERING),
        FitStage("hall", ("band_mass",)),
    ),
    "dpb_s": (FitStage("seebeck", DPB_BANDS),),
    "dpb_s_rho": (
        FitStage("seebeck", DPB_BANDS, repeats=True),
        FitStage("resistivity", DPB_SCATTERING, repeats=True),
    ),
    "dpb_s_rho_rh": (
        FitStage("seebeck", DPB_BANDS, repeats=True),
        FitStage("resistivity", DPB_SCATTERING, repeats=True),
        FitStage("hall", ("m1",)),
    ),
}
# With no Hall data, these use m1 = 1, so the size of n is not measured.
RELATIVE_CURVE_KINDS: dict[str, tuple[CurveKind, ...]] = {
    "dpb_s": ("carrier_concentration_by_band",),
    "dpb_s_rho": ("carrier_concentration_by_band",),
}


# Every parameter in K is an energy, which a user reads in eV. Temperatures are no parameters.
_ENERGY_DISPLAY: dict[str, Any] = {
    "display_unit": ENERGY_DISPLAY_UNIT,
    "display_factor": BOLTZMANN_EV_PER_K,
    "display_step": ENERGY_DISPLAY_STEP_EV,
}


def _parameter(entry: dict[str, Any]) -> ParameterSpec:
    slider = entry["slider"]
    # The web bounds replace the desktop's where the table records a deviation, such as D1.
    bounds = entry.get("web_fit_bounds") or entry.get("default_fit_bounds")
    return ParameterSpec(
        name=entry["name"],
        meaning=entry["meaning"],
        unit=entry["unit"],
        role=entry["role"],
        scattering=tuple(entry["scattering"]),
        value_range=ValueRange(slider["min"], slider["max"], slider["step"], slider["default"]),
        display_scale=entry["display_scale"],
        fit_scale=entry.get("web_fit_scale", entry["fit_scale"]),
        calc_scale=entry["calc_scale"],
        fit_bounds=Bounds(bounds["lower"], bounds["upper"]) if bounds else None,
        bounds_editable=entry.get("editable", False),
        **(_ENERGY_DISPLAY if entry["unit"] == "K" else {}),
    )


def _fit_mode(entry: dict[str, Any]) -> FitMode:
    scattering = entry["scattering"] or {}
    iteration = entry["iteration"]
    degeneracy = entry.get("degeneracy")
    return FitMode(
        id=entry["id"],
        quantities=FIT_MODE_QUANTITIES[entry["fit_mode"]],
        parameters=tuple(_parameter(parameter) for parameter in entry["parameters"]),
        scattering=tuple(scattering.get("options", ())),
        default_scattering=scattering.get("default"),
        iterative=iteration["kind"] == "iterative",
        threshold=iteration.get("threshold"),
        max_iterations=iteration.get("max_iterations"),
        degeneracy=(
            Degeneracy(degeneracy["n1_default"], degeneracy["n2_default"]) if degeneracy else None
        ),
        curve_kinds=CURVE_KINDS[entry["id"]],
        known_issues=issues_for_mode(entry["id"]),
        unavailable_curves=tuple(
            UnavailableCurve(kind, reason) for kind, reason in UNAVAILABLE_CURVES[entry["id"]]
        ),
        relative_curve_kinds=RELATIVE_CURVE_KINDS.get(entry["id"], ()),
        stages=STAGES[entry["id"]],
    )


def load_desktop_descriptions() -> dict[str, ModelDescription]:
    """Return the descriptions by model id, in the order of the table."""
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    modes = table["modes"]
    return {
        name.lower(): ModelDescription(
            id=name.lower(),
            name=full_name,
            fit_modes=tuple(_fit_mode(mode) for mode in modes if mode["model"] == name),
            default_min_temperature_k=table["fit_range"]["default_min_k"],
            default_max_temperature_k=table["fit_range"]["default_max_k"],
            default_curve_points=table["curve_points"]["count"],
            has_initial_guess=name in MODELS_WITH_INITIAL_GUESS,
            initial_guess_method="numerical" if name == "SPB" else "neural",
        )
        for name, full_name in MODEL_NAMES.items()
    }
