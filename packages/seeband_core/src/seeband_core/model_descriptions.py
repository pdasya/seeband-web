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
    ModelDescription,
    ParameterSpec,
    Quantity,
    ValueRange,
)

MODEL_NAMES = {"SPB": "Single parabolic band", "DPB": "Double parabolic band"}
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
        fit_scale=entry["fit_scale"],
        calc_scale=entry["calc_scale"],
        fit_bounds=Bounds(bounds["lower"], bounds["upper"]) if bounds else None,
        bounds_editable=entry.get("editable", False),
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
        )
        for name, full_name in MODEL_NAMES.items()
    }
