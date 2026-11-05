"""What runs in a fit's own process."""

from collections.abc import Callable

from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest, FitResult, IterationUpdate


def run_fit(
    model_id: str, request: FitRequest, send_iteration: Callable[[IterationUpdate], None]
) -> FitResult:
    return registry.get(model_id).fit(request, send_iteration)
