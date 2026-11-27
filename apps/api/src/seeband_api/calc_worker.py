"""What runs in a worker process. It imports the models once, and holds no state between calls."""

import multiprocessing
import os
import threading
import warnings
from collections.abc import Mapping
from dataclasses import dataclass

from seeband_core.fit_quality import Rmse
from seeband_core.math_module import NoFiniteChemicalPotentialError
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest, CurveResult, Measurement, Quantity
from seeband_core.partial_calculation import CalculationIssue, partial_curve, partial_rmse


class CalculationFailed(Exception):
    """Carries a safe exception type and optional finite-root domain code from the worker."""

    def __init__(self, exception_type: str, detail_code: str | None = None) -> None:
        super().__init__(exception_type)
        self.detail_code = detail_code


@dataclass(frozen=True, eq=False)
class CalcOutcome:
    curve: CurveResult
    rmse: Mapping[Quantity, Rmse]
    issues: tuple[CalculationIssue, ...] = ()


def _exit_when_parent_exits() -> None:
    parent = multiprocessing.parent_process()
    assert parent is not None
    parent.join()
    os._exit(0)


def initialise_worker() -> None:
    # A server stopped by a signal does not get to shut its pool down, so a worker would wait for
    # work for ever. This also covers a server that was killed.
    if multiprocessing.parent_process() is not None:
        threading.Thread(target=_exit_when_parent_exits, daemon=True).start()
    # The core warns on overflow for ordinary parameters, which would flood the log on every slider
    # move. A result that is not finite reaches the client as null.
    warnings.simplefilter("ignore")


def warm_up() -> None:
    """Does nothing. Submitting it makes the pool start a worker before the first request."""


def calculate(
    model_id: str,
    request: CurveRequest,
    measurements: Mapping[Quantity, Measurement],
    rmse_points: int,
) -> CalcOutcome:
    """Returns the curves, and the RMSE against any measurements. The route validates the request.

    So a `ValueError` here comes from the numbers.
    """
    model = registry.get(model_id)
    try:
        curve, curve_issues = partial_curve(model, request)
        rmse, rmse_issues = partial_rmse(model, request, measurements, rmse_points)
    except NoFiniteChemicalPotentialError as error:
        raise CalculationFailed(type(error).__name__, error.code) from error
    except (ArithmeticError, ValueError) as error:
        raise CalculationFailed(type(error).__name__) from error
    return CalcOutcome(curve, rmse, (*curve_issues, *rmse_issues))
