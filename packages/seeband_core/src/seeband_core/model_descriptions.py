"""Build the SPB and DPB descriptions from the table of desktop modes."""

import json
from importlib import resources
from typing import Any

from seeband_core.model_interface import (
    Bounds,
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
    return FitMode(
        id=entry["id"],
        quantities=FIT_MODE_QUANTITIES[entry["fit_mode"]],
        parameters=tuple(_parameter(parameter) for parameter in entry["parameters"]),
        scattering=tuple(scattering.get("options", ())),
        default_scattering=scattering.get("default"),
        iterative=iteration["kind"] == "iterative",
        threshold=iteration.get("threshold"),
        max_iterations=iteration.get("max_iterations"),
        uses_degeneracy=entry.get("degeneracy") is not None,
    )


def load_desktop_descriptions() -> dict[str, ModelDescription]:
    """Return the descriptions by model id, in the order of the table."""
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    modes = json.loads(path.read_text(encoding="utf-8"))["modes"]
    return {
        name.lower(): ModelDescription(
            id=name.lower(),
            name=full_name,
            fit_modes=tuple(_fit_mode(mode) for mode in modes if mode["model"] == name),
        )
        for name, full_name in MODEL_NAMES.items()
    }
