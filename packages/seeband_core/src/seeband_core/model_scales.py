"""Conversion between control units, core units and displayed values. Convert only here."""

from seeband_core.model_interface import FitMode, ParameterSpec, ValueRange

# The Boltzmann constant in eV/K (CODATA 2018), with which an energy in K is shown in eV.
BOLTZMANN_EV_PER_K = 8.617333262e-5
ENERGY_DISPLAY_UNIT = "eV"
# A step of 0.01 eV, to which values show: the desktop's 1 K, about 0.086 meV, is too fine to read.
ENERGY_DISPLAY_STEP_EV = 0.01


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


def control_value(spec: ParameterSpec, value: float) -> float:
    """Return the core value a control holds once set to a core value, as the desktop's slider does.

    A slider holds whole units within its range. A value that is not finite raises, as on the
    desktop. So does the desktop's slider beyond a 32-bit integer, which this limits instead.
    """
    limits = spec.value_range
    slider_value = round(scale_value(value, 1 / spec.fit_scale))
    return float(
        scale_value(max(limits.minimum, min(limits.maximum, slider_value)), spec.fit_scale)
    )


def core_to_display(spec: ParameterSpec, value: float) -> float:
    """Return the value a user sees for a core value."""
    if spec.display_scale != spec.fit_scale:
        value = scale_value(value, spec.display_scale / spec.fit_scale)
    return value * spec.display_factor if spec.display_factor != 1.0 else value


def display_to_core(spec: ParameterSpec, value: float) -> float:
    """Return the core value for a value a user entered."""
    if spec.display_factor != 1.0:
        value = value / spec.display_factor
    if spec.display_scale == spec.fit_scale:
        return value
    return scale_value(value, spec.fit_scale / spec.display_scale)


def core_range(spec: ParameterSpec) -> ValueRange:
    """Return the range of a parameter's control in core units."""
    limits = spec.value_range
    return ValueRange(
        scale_value(limits.minimum, spec.fit_scale),
        scale_value(limits.maximum, spec.fit_scale),
        scale_value(limits.step, spec.fit_scale),
        scale_value(limits.default, spec.fit_scale),
    )


def display_range(spec: ParameterSpec) -> ValueRange:
    """Return the range of a parameter's control as a user sees it, in its display unit."""
    scaled = spec.value_range
    factor = spec.display_factor

    def shown(value: float) -> float:
        value = scale_value(value, spec.display_scale)
        return value * factor if factor != 1.0 else value

    return ValueRange(
        shown(scaled.minimum),
        shown(scaled.maximum),
        spec.display_step if spec.display_step is not None else shown(scaled.step),
        shown(scaled.default),
    )
