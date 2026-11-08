"""Numerical SPB initial estimates from Seebeck measurements.

S determines carrier sign and Fermi energy, but not absolute band mass.
The returned mass is a signed unit reference; clients preserve its magnitude.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.optimize import least_squares

from seeband_core import math_module
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Measurement
from seeband_core.model_scales import control_value, core_range

EstimateWarning = Literal["low_temperature_omitted", "estimate_at_bound", "large_estimate_residual"]
EstimateReason = Literal["too_few_temperatures", "sign_change", "zero_seebeck"]


@dataclass
class NumericalEstimate:
    start_values: dict[str, float] = field(default_factory=dict)
    warnings: list[EstimateWarning] = field(default_factory=list)
    reason: EstimateReason | None = None
    rmse_v_per_k: float | None = None

    def __getitem__(self, name: str) -> float:
        return self.start_values[name]


def single_band_guess(
    model_id: str, temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray
) -> NumericalEstimate:
    """Estimate E_F on up to 24 measured points using bounded log coordinates."""
    if model_id != "spb":
        raise ValueError("An SPB model is required")
    Measurement(temperature_k, seebeck_v_per_k).check("seebeck")
    order = np.argsort(temperature_k, kind="stable")
    t, s = temperature_k[order], seebeck_v_per_k[order]
    ef_max = core_range(registry.get(model_id).describe().fit_modes[0].parameters[1]).maximum
    safe = t >= ef_max / 700
    warnings: list[EstimateWarning] = [] if np.all(safe) else ["low_temperature_omitted"]
    t, s = t[safe], s[safe]
    if len(np.unique(t)) < 3:
        return NumericalEstimate(reason="too_few_temperatures", warnings=warnings)
    if np.any(s > 0) and np.any(s < 0):
        return NumericalEstimate(reason="sign_change", warnings=warnings)
    if not np.any(s):
        return NumericalEstimate(reason="zero_seebeck", warnings=warnings)
    sign = -1.0 if np.mean(s) > 0 else 1.0
    indexes = np.unique(np.linspace(0, len(t) - 1, min(len(t), 24)).astype(int))
    t, s = t[indexes], s[indexes]
    specs = {p.name: p for p in registry.get(model_id).describe().fit_modes[0].parameters}
    ef_limits = core_range(specs["fermi_energy"])

    def residual(x: np.ndarray) -> np.ndarray:
        predicted = math_module.spb_see_vs_temp(t, sign * float(np.exp(x[0])), sign)
        residuals: np.ndarray = (predicted - s) * 1e6
        return residuals

    result = least_squares(
        residual, [np.log(300.0)], bounds=([0.0], [np.log(ef_limits.maximum)]), max_nfev=60
    )
    if not result.success or not np.all(np.isfinite(result.fun)):
        raise ValueError("No finite SPB estimate")
    values = {"band_mass": sign, "fermi_energy": sign * float(np.exp(result.x[0]))}
    values = {name: control_value(specs[name], value) for name, value in values.items()}
    full_t, full_s = (
        temperature_k[temperature_k >= ef_max / 700],
        seebeck_v_per_k[temperature_k >= ef_max / 700],
    )
    order = np.argsort(full_t)
    errors = (
        math_module.spb_see_vs_temp(full_t[order], values["fermi_energy"], sign) - full_s[order]
    )
    rmse = float(np.sqrt(np.mean(errors**2)))
    if np.any(result.active_mask) or abs(values["fermi_energy"]) in (1, ef_limits.maximum):
        warnings.append("estimate_at_bound")
    # A descriptive residual heuristic, not a diagnosis of band count.
    if rmse > 0.2 * float(np.sqrt(np.mean(full_s**2))):
        warnings.append("large_estimate_residual")
    return NumericalEstimate(values, warnings, rmse_v_per_k=rmse)
