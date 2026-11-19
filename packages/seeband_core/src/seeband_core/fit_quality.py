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
# Custom-model fallback interpolates a curve grid to the submitted temperatures.
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

    Built-in SPB/DPB kernels evaluate at each quantity's measured temperatures.
    Other registered models retain interpolation from a curve grid; `points`
    controls that fallback only. Pass only the data inside the intended fit range.
    """
    if not measurements:
        raise ValueError("RMSE needs at least one measurement")
    for quantity, measurement in measurements.items():
        measurement.check(quantity)
    from seeband_core.band_models import DpbModel, SpbModel
    from seeband_core.verified_fit import evaluate

    if isinstance(model, SpbModel | DpbModel):
        mode = model.describe().fit_mode(fit_mode)
        if scattering is None and mode.scattering and not mode.id.endswith("_s"):
            raise ValueError(f"Fit mode {fit_mode} needs a scattering type")
        mode.parameters_for(scattering)
        ratio = 1.0
        if isinstance(model, DpbModel):
            if band_1_degeneracy <= 0 or band_2_degeneracy <= 0:
                raise ValueError("Band degeneracies must be positive")
            ratio = band_2_degeneracy / band_1_degeneracy
        results: dict[Quantity, Rmse] = {}
        for quantity, measurement in measurements.items():
            if quantity not in mode.quantities:
                raise ValueError(f"Fit mode {fit_mode} has no curve for {quantity}")
            values = evaluate(
                model.describe().id,
                fit_mode,
                parameters,
                measurement.temperature_k,
                scattering,
                ratio,
                quantities=(quantity,),
                check_finite=False,
                band_1_degeneracy=band_1_degeneracy if isinstance(model, DpbModel) else 1.0,
            )[quantity]
            # Percentage residuals are undefined at a measured zero. Verified
            # fit diagnostics supply absolute RMSE and safe relative L2 instead.
            results[quantity] = (
                Rmse(None, "%")
                if quantity != "seebeck" and np.any(measurement.values == 0)
                else rmse(quantity, values, measurement.values)
            )
        return results
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
    results = {}
    for quantity, measurement in measurements.items():
        if CURVE_NAMES[quantity] not in curve.curves:
            raise ValueError(f"Fit mode {fit_mode} has no curve for {quantity}")
        model_values = np.interp(
            measurement.temperature_k, curve.temperature_k, curve.curves[CURVE_NAMES[quantity]]
        )
        results[quantity] = rmse(quantity, model_values, measurement.values)
    return results
