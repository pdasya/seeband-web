"""Points derived from measured data alone, with no model, for a client to draw beside a curve."""

import math
from collections.abc import Sequence

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
