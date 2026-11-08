"""Numerical SPB initial estimates from Seebeck measurements.

S determines carrier sign and Fermi energy, but not absolute band mass.
The returned mass is a signed unit reference; clients preserve its magnitude.
"""

import numpy as np
from scipy.optimize import least_squares

from seeband_core import math_module
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Measurement
from seeband_core.model_scales import control_value, core_range


def single_band_guess(
    model_id: str, temperature_k: np.ndarray, seebeck_v_per_k: np.ndarray
) -> dict[str, float]:
    """Estimate E_F on up to 24 measured points using bounded log coordinates."""
    if model_id != "spb":
        raise ValueError("An SPB model is required")
    Measurement(temperature_k, seebeck_v_per_k).check("seebeck")
    order = np.argsort(temperature_k, kind="stable")
    t, s = temperature_k[order], seebeck_v_per_k[order]
    if len(np.unique(t)) < 3:
        raise ValueError("At least three distinct temperatures are required")
    if np.any(s > 0) and np.any(s < 0):
        raise ValueError("A single band cannot reproduce a Seebeck sign change")
    if not np.any(s):
        raise ValueError("Zero Seebeck does not determine a finite Fermi energy")
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
    return {name: control_value(specs[name], value) for name, value in values.items()}
