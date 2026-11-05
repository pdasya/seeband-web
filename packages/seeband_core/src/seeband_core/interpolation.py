"""Replace measured data by a smooth curve on an even grid, as the desktop's interpolation does.

docs/interpolation.md gives the exact semantics. The grid covers the fit range even beyond the data,
which extrapolates. That is a known error, which P7 fixes.
"""

import warnings
from dataclasses import dataclass

import numpy as np

from seeband_core import data_processing
from seeband_core.model_interface import Measurement

INTERPOLATION_DEGREE = 10
GRID_STEP_K = 20.0


@dataclass(frozen=True, eq=False)
class InterpolatedData:
    """The data on the grid. `extrapolated` means that some of the grid lies outside the data, and
    `underdetermined` that the data have too few distinct temperatures to set the polynomial."""

    measurement: Measurement
    extrapolated: bool
    underdetermined: bool


def interpolation_grid_k(min_temperature_k: float, max_temperature_k: float) -> np.ndarray:
    """Return the grid: a step of about 20 K, as the desktop's `int((max - min) / 20)` points."""
    if not min_temperature_k < max_temperature_k:
        raise ValueError("The fit range must have its minimum below its maximum")
    points = int((max_temperature_k - min_temperature_k) / GRID_STEP_K)
    if points < 1:
        raise ValueError(f"The fit range must span at least {GRID_STEP_K} K to interpolate")
    return np.linspace(min_temperature_k, max_temperature_k, points)


def interpolate(
    measurement: Measurement, min_temperature_k: float, max_temperature_k: float
) -> InterpolatedData:
    """Interpolate one quantity over the fit range, from all of its data."""
    measurement.check("interpolation")
    grid_k = interpolation_grid_k(min_temperature_k, max_temperature_k)
    data = np.column_stack((measurement.temperature_k, measurement.values))
    with warnings.catch_warnings():
        # The result reports this as `underdetermined`.
        warnings.simplefilter("ignore", np.exceptions.RankWarning)
        fit = data_processing.fit_data(data, INTERPOLATION_DEGREE)
    if fit is None:
        raise ValueError("The data could not be fitted")
    interpolated = data_processing.interpolate_data(fit, grid_k)
    return InterpolatedData(
        Measurement(interpolated[:, 0], interpolated[:, 1]),
        extrapolated=bool(
            grid_k[0] < np.min(measurement.temperature_k)
            or grid_k[-1] > np.max(measurement.temperature_k)
        ),
        underdetermined=len(np.unique(measurement.temperature_k)) <= INTERPOLATION_DEGREE,
    )


def in_fit_range(
    measurement: Measurement, min_temperature_k: float, max_temperature_k: float
) -> Measurement:
    """Return the data a fit reads when not interpolating: points in the range, inclusive."""
    inside = (measurement.temperature_k >= min_temperature_k) & (
        measurement.temperature_k <= max_temperature_k
    )
    return Measurement(measurement.temperature_k[inside], measurement.values[inside])
