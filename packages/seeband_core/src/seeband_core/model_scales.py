"""Conversion between control units, core units and displayed values. Convert only here."""

from seeband_core.model_interface import FitMode, ParameterSpec, ValueRange


def scale_value(value: float, scale: float) -> float:
    """Multiply by a scale, dividing where it is a fraction, as the desktop does with slider / 100.

    The two differ in the last bit for some values, and that can change a fit slightly.
    """
    if 0 < scale < 1:
        return value / round(1 / scale)
    return value * scale


def default_start_value(spec: ParameterSpec) -> float:
    """Return the core value of a parameter's default."""
    return scale_value(spec.value_range.default, spec.fit_scale)


def default_start(fit_mode: FitMode) -> dict[str, float]:
    """Return every parameter of a mode, as a `start` for a fit or `parameters` for a curve."""
    return {spec.name: default_start_value(spec) for spec in fit_mode.parameters}


def core_to_display(spec: ParameterSpec, value: float) -> float:
    """Return the value a user sees for a core value."""
    if spec.display_scale == spec.fit_scale:
        return value
    return scale_value(value, spec.display_scale / spec.fit_scale)


def display_to_core(spec: ParameterSpec, value: float) -> float:
    """Return the core value for a value a user entered."""
    if spec.display_scale == spec.fit_scale:
        return value
    return scale_value(value, spec.fit_scale / spec.display_scale)


def display_range(spec: ParameterSpec) -> ValueRange:
    """Return the range of a parameter's control as a user sees it."""
    scaled = spec.value_range
    return ValueRange(
        scale_value(scaled.minimum, spec.display_scale),
        scale_value(scaled.maximum, spec.display_scale),
        scale_value(scaled.step, spec.display_scale),
        scale_value(scaled.default, spec.display_scale),
    )
