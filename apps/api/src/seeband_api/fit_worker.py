"""What runs in a fit's own process. It imports nothing of the web framework."""

from collections.abc import Callable
from multiprocessing.connection import Connection

from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest, FitResult, IterationUpdate

from seeband_api.calc_worker import initialise_worker


def run_fit(
    model_id: str, request: FitRequest, send_iteration: Callable[[IterationUpdate], None]
) -> FitResult:
    return registry.get(model_id).fit(request, send_iteration)


def run_in_child(job: Connection, events: Connection) -> None:
    """Runs the job from one pipe, and sends what happens through the other.

    It lives here, not in `fit_runner`, as the child imports the module of its target first, and
    `fit_runner` would bring FastAPI, about 0.1 s that the fork server has not loaded.

    Only an exception's type crosses, not its text. The job comes through a pipe rather than the
    process's arguments, because passing those holds up `start` until the child reads them, and
    until `start` returns, the process cannot be killed.
    """
    initialise_worker()
    try:
        function, args = job.recv()
    except EOFError:
        return
    finally:
        job.close()
    try:
        result = function(*args, lambda update: events.send(("iteration", update)))
    except BaseException as error:
        events.send(("error", type(error).__name__))
    else:
        events.send(("result", result))
    events.close()
