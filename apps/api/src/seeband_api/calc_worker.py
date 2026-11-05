"""What runs in a worker process. It imports the models once, and holds no state between calls."""

import multiprocessing
import os
import threading
import warnings
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from seeband_core.fit_quality import Rmse, curve_rmse
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest, CurveResult, Measurement, Quantity


class CalculationFailed(Exception):
    """The core has no result, as at m_eff = 0, or for many DPB S + rho + R_H curves at low T.

    It carries only the type of the core's exception, as the core's text can quote values.
    """


@dataclass(frozen=True, eq=False)
class CalcOutcome:
    curve: CurveResult
    rmse: Mapping[Quantity, Rmse]


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
        curve = model.calculate(request)
        # A negative m1 gives complex values, whose real part would look like a plausible result.
        if any(np.iscomplexobj(values) for values in curve.curves.values()):
            raise ValueError("The curve has complex values")
        rmse = (
            curve_rmse(
                model,
                request.fit_mode,
                request.parameters,
                measurements,
                request.scattering,
                request.band_1_degeneracy,
                request.band_2_degeneracy,
                rmse_points,
            )
            if measurements
            else {}
        )
    except (ArithmeticError, ValueError) as error:
        raise CalculationFailed(type(error).__name__) from error
    return CalcOutcome(curve, rmse)
