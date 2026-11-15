"""Where calculation processes come from: a fork server that has loaded the core once.

Starting a fresh interpreter for each fit cost about 0.44 s, mostly importing scipy.optimize. A fork
server starts once, imports what calculations need, and forks each new process from itself, so the
process starts with the core loaded. Each fit still gets its own process, which can be killed.

`fork` from the server itself is not used, as the server has threads, which `fork` does not copy
safely. The fork server is a separate process with one thread, started by exec as `spawn` would.
The environment it inherits keeps numpy's linear algebra to one thread, so nothing it forks from
holds a thread pool either.
"""

import multiprocessing
import os
import threading
from multiprocessing import forkserver
from multiprocessing.context import ForkServerContext

# Each process runs one job at a time, so numpy's linear algebra takes one thread there. Otherwise
# each starts a thread for every core, and the processes fight over them. Set here as well as in
# `__main__`, for a server started another way, such as by the `uvicorn` command: the fork server
# takes the environment when it starts, and so does each process forked from it.
ONE_THREAD = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
for _name in ONE_THREAD:
    os.environ.setdefault(_name, "1")

# How long the fork server may take for its imports at most, about 0.3 s on a Mac.
START_TIMEOUT_S = 60.0

# What a fit or a calculation imports, so that the fork server holds it already. The verified fit
# is imported lazily by the core, and scipy.optimize is most of the time.
#
# Not `__main__`, the fork server's default: it would run a main script without a `__name__` guard
# inside the fork server, and so start a second server. Each child sets up `__main__` as under
# `spawn` instead. That costs nothing for `python -m seeband_api` or `python -m uvicorn`, whose main
# module is a package's `__main__`, which a child does not import again. A script, such as the
# `uvicorn` command, is run again in each child as `__mp_main__`, so it needs its guard, as it did
# under `spawn`.
PRELOADED = (
    "seeband_api.calc_worker",
    "seeband_api.fit_worker",
    "seeband_core.verified_fit",
    "scipy.optimize",
)

context: ForkServerContext = multiprocessing.get_context("forkserver")
context.set_forkserver_preload(list(PRELOADED))


def _nothing() -> None:
    pass


def start_fork_server(timeout_s: float = START_TIMEOUT_S) -> None:
    """Starts the fork server and waits for its imports, rather than leaving them to a request.

    Starting the server returns before it has imported anything, so this forks one process that
    does nothing: the fork waits until the imports are done. A fork server that has died is started
    again. Raises `TimeoutError` if the imports take longer than `timeout_s`, which a fork cannot be
    told, so the waiting happens in a thread.
    """
    failures: list[BaseException] = []
    done = threading.Event()

    def start() -> None:
        try:
            forkserver.ensure_running()
            process = context.Process(target=_nothing, daemon=True)
            process.start()
            process.join()
            process.close()
        except BaseException as error:
            failures.append(error)
        finally:
            done.set()

    threading.Thread(target=start, name="fork-server-start", daemon=True).start()
    if not done.wait(timeout_s):
        raise TimeoutError("The fork server did not finish its imports")
    if failures:
        raise failures[0]
