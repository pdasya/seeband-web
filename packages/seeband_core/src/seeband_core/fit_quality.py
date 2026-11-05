"""Measures of how well a curve matches measured data, with or without a fit."""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from seeband_core.model_interface import CurveRequest, Measurement, Model, Quantity

CURVE_NAMES: Mapping[Quantity, str] = {
    "seebeck": "seebeck_v_per_k",
    "resistivity": "resistivity_ohm_m",
    "hall": "hall_m3_per_c",
}
# Curves come on an even grid, and are read at measured temperatures from this many points.
RMSE_GRID_POINTS = 200


@dataclass(frozen=True)
class Rmse:
    value: float
    unit: str


def rmse(quantity: Quantity, model_values: np.ndarray, measured_values: np.ndarray) -> Rmse:
    """Return the root mean square difference: S in µV/K, rho and R_H as a percent of the data."""
    if len(model_values) == 0 or len(model_values) != len(measured_values):
        raise ValueError("RMSE needs the same number of model and measured values")
    if quantity == "seebeck":
        difference = (model_values - measured_values) * 1e6
        return Rmse(float(np.sqrt(np.mean(difference**2))), "uV/K")
    relative = (model_values - measured_values) / measured_values * 100
    return Rmse(float(np.sqrt(np.mean(relative**2))), "%")


def curve_rmse(
    model: Model,
    request: CurveRequest,
    quantity: Quantity,
    measurement: Measurement,
) -> Rmse:
    """Return the RMSE of a model's measured curve against data, for any parameters.

    `request` gives the mode, parameters and scattering. Its temperature range and points are
    replaced by the range of the data and `RMSE_GRID_POINTS`.
    """
    temperature_k = measurement.temperature_k
    curve = model.calculate(
        CurveRequest(
            request.fit_mode,
            request.parameters,
            float(np.min(temperature_k)),
            float(np.max(temperature_k)),
            RMSE_GRID_POINTS,
            request.scattering,
            "measured",
            request.band_1_degeneracy,
            request.band_2_degeneracy,
        )
    )
    name = CURVE_NAMES[quantity]
    model_values = np.interp(temperature_k, curve.temperature_k, curve.curves[name])
    return rmse(quantity, model_values, measurement.values)
