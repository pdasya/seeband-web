"""Points derived from measured data alone, with no model, for a client to draw beside a curve."""

import math
from collections.abc import Sequence

import numpy as np

# The column of each kind of point, named with its unit as a curve's is.
CONDUCTIVITY_COLUMN = "electrical_conductivity_s_per_m"


def conductivity_points(resistivity_ohm_m: Sequence[float]) -> list[float | None]:
    """Return sigma = 1/rho in S/m for each measured rho in ohm*m.

    A rho of 0 or below, or one that is not finite, has no conductivity, so its point is None
    rather than an error or an infinite value. The input is not changed.
    """
    return [
        1.0 / value if math.isfinite(value) and value > 0 else None for value in resistivity_ohm_m
    ]


def resistivity_from_conductivity(conductivity_s_per_m: np.ndarray) -> np.ndarray:
    """Return rho = 1/sigma in ohm*m for each measured sigma in S/m.

    This is the one place a loaded conductivity becomes the resistivity that fits, curves and the
    RMSE use. Each value is the float nearest 1/sigma, as one division by hand gives it, so a fit
    from sigma is the fit from 1/sigma loaded as rho. A sigma of 0 or below, one that is not finite,
    or one so small that 1/sigma is not, raises ValueError, as it has no resistivity. The input is
    not changed.
    """
    sigma = np.asarray(conductivity_s_per_m, dtype=np.float64)
    with np.errstate(divide="ignore", over="ignore"):
        resistivity = 1.0 / sigma
    if not np.all((sigma > 0) & np.isfinite(sigma) & np.isfinite(resistivity)):
        raise ValueError(
            "A conductivity of 0 or below, not finite or under about 6e-309 S/m has no resistivity"
        )
    return resistivity
