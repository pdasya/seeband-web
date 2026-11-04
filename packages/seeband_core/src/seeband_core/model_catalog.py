"""Register the built-in models. Import `registry` from here in anything that runs models.

Worker processes import this too, so they hold the same models however they were started.
"""

from seeband_core.band_models import DpbModel, SpbModel
from seeband_core.model_registry import registry

registry.register(SpbModel())
registry.register(DpbModel())

__all__ = ["registry"]
