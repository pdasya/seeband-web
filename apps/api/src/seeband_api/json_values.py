"""Values in the form that JSON can hold."""

import numpy as np


def finite_or_none(values: np.ndarray) -> list[float | None]:
    """Replaces values that are not finite with None, as JSON has no NaN or infinity."""
    return [float(value) if np.isfinite(value) else None for value in values]
