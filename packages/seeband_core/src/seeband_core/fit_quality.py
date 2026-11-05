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
# Curves come on an even grid, and are interpolated to measured temperatures from this many points.
RMSE_GRID_POINTS = 200


@dataclass(frozen=True)
class Rmse:
    """`value` is None where the model has no finite value to compare, which JSON could not hold."""

    value: float | None
    unit: str


def rmse(quantity: Quantity, model_values: np.ndarray, measured_values: np.ndarray) -> Rmse:
    """Return the root mean square difference: S in µV/K, rho and R_H as a percent of the data.

    A percent has no meaning at a measured value of 0, which is an error. Near a sign change of R_H,
    points with tiny values dominate it.
    """
    if len(model_values) == 0 or len(model_values) != len(measured_values):
        raise ValueError("RMSE needs the same number of model and measured values")
    if not np.all(np.isfinite(measured_values)):
        raise ValueError("RMSE needs finite measured values")
    unit = "uV/K" if quantity == "seebeck" else "%"
    if quantity != "seebeck" and np.any(measured_values == 0):
        raise ValueError("A relative RMSE needs measured values other than 0")
    if not np.all(np.isfinite(model_values)):
        return Rmse(None, unit)
    if quantity == "seebeck":
        difference = (model_values - measured_values) * 1e6
    else:
        difference = (model_values - measured_values) / measured_values * 100
    return Rmse(float(np.sqrt(np.mean(difference**2))), unit)


def curve_rmse(
    model: Model,
    fit_mode: str,
    parameters: Mapping[str, float],
    measurements: Mapping[Quantity, Measurement],
    scattering: str | None = None,
    band_1_degeneracy: float = 1.0,
    band_2_degeneracy: float = 1.0,
    points: int = RMSE_GRID_POINTS,
) -> dict[Quantity, Rmse]:
    """Return the RMSE of a model against each measured quantity, for any parameters.

    This calculates one curve over the range of all the data, and interpolates it to the measured
    temperatures. Pass only the points inside the fit range to get an RMSE over that range. With
    fewer points it is faster and less accurate.
    """
    if not measurements:
        raise ValueError("RMSE needs at least one measurement")
    for quantity, measurement in measurements.items():
        measurement.check(quantity)
    temperatures = [measurement.temperature_k for measurement in measurements.values()]
    curve = model.calculate(
        CurveRequest(
            fit_mode,
            parameters,
            float(min(np.min(values) for values in temperatures)),
            float(max(np.max(values) for values in temperatures)),
            points,
            scattering,
            "measured",
            band_1_degeneracy,
            band_2_degeneracy,
        )
    )
    results: dict[Quantity, Rmse] = {}
    for quantity, measurement in measurements.items():
        if CURVE_NAMES[quantity] not in curve.curves:
            raise ValueError(f"Fit mode {fit_mode} has no curve for {quantity}")
        model_values = np.interp(
            measurement.temperature_k, curve.temperature_k, curve.curves[CURVE_NAMES[quantity]]
        )
        results[quantity] = rmse(quantity, model_values, measurement.values)
    return results
