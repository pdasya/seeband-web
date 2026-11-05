"""Replace measured data by a smooth curve on an even grid, as the desktop's interpolation does.

docs/interpolation.md gives the exact semantics. The grid covers the fit range even beyond the data,
which extrapolates. That is a known error, which P7 fixes.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.polynomial import Chebyshev

from seeband_core import data_processing
from seeband_core.model_interface import Measurement

INTERPOLATION_DEGREE = 10
GRID_STEP_K = 20.0
# A limit on what one request can cost: this many points is a range of 200000 K.
MAX_GRID_POINTS = 10_000


@dataclass(frozen=True, eq=False)
class InterpolatedData:
    """The data on the grid, and what a client must show about it.

    `extrapolated` means that some of the grid lies outside the data. `measured_points_in_range` of
    0 means that the values are made up entirely. `underdetermined` means that the data do not set
    the polynomial.
    """

    measurement: Measurement
    extrapolated: bool
    measured_points_in_range: int
    underdetermined: bool


def interpolation_grid_k(min_temperature_k: float, max_temperature_k: float) -> np.ndarray:
    """Return the grid: a step of about 20 K, as the desktop's `int((max - min) / 20)` points."""
    if not (math.isfinite(min_temperature_k) and math.isfinite(max_temperature_k)):
        raise ValueError("The fit range must have finite limits")
    if min_temperature_k <= 0:
        raise ValueError("The fit range must start above 0 K to interpolate")
    if not min_temperature_k < max_temperature_k:
        raise ValueError("The fit range must have its minimum below its maximum")
    points = int((max_temperature_k - min_temperature_k) / GRID_STEP_K)
    if points < 1:
        raise ValueError(f"The fit range must span at least {GRID_STEP_K} K to interpolate")
    if points > MAX_GRID_POINTS:
        raise ValueError("The fit range is too wide to interpolate")
    return np.linspace(min_temperature_k, max_temperature_k, points)


def interpolate(
    measurement: Measurement, min_temperature_k: float, max_temperature_k: float
) -> InterpolatedData:
    """Interpolate one quantity over the fit range, from all of its data."""
    measurement.check("data")
    grid_k = interpolation_grid_k(min_temperature_k, max_temperature_k)
    temperature_k = measurement.temperature_k
    try:
        # With full=True, numpy gives the rank here, and does not warn about it.
        fit, (_, rank, _, _) = Chebyshev.fit(
            temperature_k, measurement.values, INTERPOLATION_DEGREE, full=True
        )
    except np.linalg.LinAlgError as error:
        raise ValueError("The data could not be fitted") from error
    interpolated = data_processing.interpolate_data(fit, grid_k)
    inside = (temperature_k >= min_temperature_k) & (temperature_k <= max_temperature_k)
    return InterpolatedData(
        Measurement(interpolated[:, 0], interpolated[:, 1]),
        extrapolated=bool(grid_k[0] < np.min(temperature_k) or grid_k[-1] > np.max(temperature_k)),
        measured_points_in_range=int(np.count_nonzero(inside)),
        underdetermined=bool(rank <= INTERPOLATION_DEGREE),
    )


def in_fit_range(
    measurement: Measurement, min_temperature_k: float, max_temperature_k: float
) -> Measurement:
    """Return the data a fit reads when not interpolating: points in the range, inclusive."""
    inside = (measurement.temperature_k >= min_temperature_k) & (
        measurement.temperature_k <= max_temperature_k
    )
    return Measurement(measurement.temperature_k[inside], measurement.values[inside])
