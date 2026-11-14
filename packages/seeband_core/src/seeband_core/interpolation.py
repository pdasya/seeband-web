"""Fit all measured data and evaluate on the overlap of the measured and requested ranges."""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.polynomial import Chebyshev

from seeband_core import data_processing
from seeband_core.model_interface import Measurement

INTERPOLATION_DEGREE = 10
GRID_STEP_K = 20.0
# A limit on what one request can cost: this many points is a range of 200000 K.
MAX_GRID_POINTS = 10_000
# An overlap the data narrow must give at least this many grid points, so that a fit gets more
# than one value; the desktop rule gives one point from 20 K and two from 40 K.
MIN_LIMITED_GRID_POINTS = 2

# Why a quantity could not be interpolated, as a client shows it.
InterpolationFailure = Literal["no_overlap", "overlap_too_short", "fit_failed"]


class InterpolationRefused(ValueError):
    """A quantity that cannot be interpolated over the range, and why."""

    def __init__(self, reason: InterpolationFailure, message: str) -> None:
        super().__init__(message)
        self.reason: InterpolationFailure = reason


@dataclass(frozen=True, eq=False)
class InterpolatedData:
    """The data on the grid, and what a client must show about it.

    `range_limited` means the requested range extends beyond the measured range. `extrapolated`
    is retained for compatibility and is always false for new results. `measured_points_in_range`
    counts source points in the requested range; zero can occur between sparse measurements.
    `underdetermined` means that the data do not set the polynomial.
    """

    measurement: Measurement
    extrapolated: bool
    measured_points_in_range: int
    underdetermined: bool
    range_limited: bool


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
    """Interpolate one quantity within its measured range, fitting all of its data."""
    measurement.check("data")
    # Validate the original request, including its cost limit, before clipping it.
    interpolation_grid_k(min_temperature_k, max_temperature_k)
    temperature_k = measurement.temperature_k
    measured_min_k = float(np.min(temperature_k))
    measured_max_k = float(np.max(temperature_k))
    low_k = max(min_temperature_k, measured_min_k)
    high_k = min(max_temperature_k, measured_max_k)
    if low_k >= high_k:
        raise InterpolationRefused(
            "no_overlap", "The fit range has no usable overlap with the measured temperature range"
        )
    limited = low_k > min_temperature_k or high_k < max_temperature_k
    shortest_k = GRID_STEP_K * (MIN_LIMITED_GRID_POINTS if limited else 1)
    if high_k - low_k < shortest_k:
        raise InterpolationRefused(
            "overlap_too_short", f"The measured overlap must span at least {shortest_k} K"
        )
    grid_k = interpolation_grid_k(low_k, high_k)
    try:
        # With full=True, numpy gives the rank here, and does not warn about it.
        fit, (_, rank, _, _) = Chebyshev.fit(
            temperature_k, measurement.values, INTERPOLATION_DEGREE, full=True
        )
    except np.linalg.LinAlgError as error:
        raise InterpolationRefused("fit_failed", "The data could not be fitted") from error
    interpolated = data_processing.interpolate_data(fit, grid_k)
    inside = (temperature_k >= min_temperature_k) & (temperature_k <= max_temperature_k)
    return InterpolatedData(
        Measurement(interpolated[:, 0], interpolated[:, 1]),
        extrapolated=False,
        measured_points_in_range=int(np.count_nonzero(inside)),
        underdetermined=bool(rank <= INTERPOLATION_DEGREE),
        range_limited=min_temperature_k < measured_min_k or max_temperature_k > measured_max_k,
    )


def in_fit_range(
    measurement: Measurement, min_temperature_k: float, max_temperature_k: float
) -> Measurement:
    """Return the data a fit reads when not interpolating: points in the range, inclusive."""
    inside = (measurement.temperature_k >= min_temperature_k) & (
        measurement.temperature_k <= max_temperature_k
    )
    return Measurement(measurement.temperature_k[inside], measurement.values[inside])
