"""A registry of models. Import the one that holds the built-in models from `model_catalog`."""

from math import isclose

from seeband_core.model_interface import Model, ModelDescription


def _check_scale(scale: float, where: str) -> None:
    """Reject what `scale_value` cannot honour: it treats a fraction as 1/n."""
    if scale <= 0 or (scale < 1 and not isclose(round(1 / scale) * scale, 1.0)):
        raise ValueError(f"{where} has a scale of {scale}, which is not above 0 or 1/n")


def _check(description: ModelDescription) -> None:
    if not description.id:
        raise ValueError("A model needs an id")
    if not description.fit_modes:
        raise ValueError(f"Model {description.id} has no fit modes")
    fit_mode_ids = [fit_mode.id for fit_mode in description.fit_modes]
    if len(set(fit_mode_ids)) != len(fit_mode_ids):
        raise ValueError(f"Model {description.id} repeats a fit mode: {fit_mode_ids}")
    for fit_mode in description.fit_modes:
        names = [spec.name for spec in fit_mode.parameters]
        if len(set(names)) != len(names):
            raise ValueError(f"Fit mode {fit_mode.id} repeats a parameter: {names}")
        for unavailable in fit_mode.unavailable_curves:
            if unavailable.kind in fit_mode.curve_kinds:
                raise ValueError(f"Fit mode {fit_mode.id} both has and lacks {unavailable.kind}")
        for kind in fit_mode.relative_curve_kinds:
            if kind not in fit_mode.curve_kinds:
                raise ValueError(f"Fit mode {fit_mode.id} has no curve {kind} to call relative")
        default = fit_mode.default_scattering
        if default is not None and default not in fit_mode.scattering:
            raise ValueError(f"Fit mode {fit_mode.id} defaults to unknown scattering {default}")
        for spec in fit_mode.parameters:
            _check_scale(spec.display_scale, f"Parameter {spec.name} in {fit_mode.id}")
            _check_scale(spec.fit_scale, f"Parameter {spec.name} in {fit_mode.id}")
            limits = spec.value_range
            if not limits.minimum <= limits.default <= limits.maximum or limits.step <= 0:
                raise ValueError(f"Parameter {spec.name} in {fit_mode.id} has an invalid range")
            if spec.fit_bounds is not None and spec.fit_bounds.lower > spec.fit_bounds.upper:
                raise ValueError(f"Parameter {spec.name} in {fit_mode.id} has inverted bounds")


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, Model] = {}
        self._descriptions: dict[str, ModelDescription] = {}

    def register(self, model: Model) -> None:
        if not isinstance(model, Model):
            raise TypeError(f"{model!r} does not implement the Model protocol")
        description = model.describe()
        _check(description)
        if description.id in self._models:
            raise ValueError(f"Model {description.id} is already registered")
        self._models[description.id] = model
        self._descriptions[description.id] = description

    def get(self, model_id: str) -> Model:
        if model_id not in self._models:
            raise KeyError(f"Unknown model: {model_id}")
        return self._models[model_id]

    def descriptions(self) -> tuple[ModelDescription, ...]:
        """Return the descriptions in the order the models were registered."""
        return tuple(self._descriptions.values())


registry = ModelRegistry()
