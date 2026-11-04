"""The models the application knows about. API and client code find models only through here."""

from seeband_core.model_interface import Model, ModelDescription


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, Model] = {}

    def register(self, model: Model) -> None:
        description = model.describe()
        if description.id in self._models:
            raise ValueError(f"Model {description.id} is already registered")
        fit_mode_ids = [fit_mode.id for fit_mode in description.fit_modes]
        if len(set(fit_mode_ids)) != len(fit_mode_ids):
            raise ValueError(f"Model {description.id} repeats a fit mode: {fit_mode_ids}")
        self._models[description.id] = model

    def get(self, model_id: str) -> Model:
        if model_id not in self._models:
            raise KeyError(f"Unknown model: {model_id}")
        return self._models[model_id]

    def descriptions(self) -> tuple[ModelDescription, ...]:
        return tuple(model.describe() for model in self._models.values())


registry = ModelRegistry()
