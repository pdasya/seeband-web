"""Where calculation processes come from: a fork server that has loaded the core once.

Starting a fresh interpreter for each fit cost about 0.44 s, mostly importing scipy.optimize. A fork
server starts once, imports what calculations need, and forks each new process from itself, so the
process starts with the core loaded. Each fit still gets its own process, which can be killed.

`fork` from the server itself is not used, as the server has threads, which `fork` does not copy
safely. The fork server is a separate process with one thread, started by exec as `spawn` would.
The environment it inherits keeps numpy's linear algebra to one thread (see `__main__`), so nothing
it forks from holds a thread pool either.
"""

import multiprocessing
from multiprocessing import forkserver
from multiprocessing.context import ForkServerContext

# What a fit or a calculation imports, so that the fork server holds it already. The verified fit
# is imported lazily by the core, and scipy.optimize is most of the time.
#
# Not `__main__`, the fork server's default: it would run a main script without a `__name__` guard
# inside the fork server, and so start a second server. Each child sets up `__main__` as under
# `spawn` instead. That costs nothing for `python -m seeband_api` or uvicorn's command, whose main
# module is a package's `__main__`, which a child does not import again.
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


def start_fork_server() -> None:
    """Starts the fork server and waits for its imports, rather than leaving them to a request.

    Starting the server returns before it has imported anything, so this forks one process that
    does nothing: the fork waits until the imports are done.
    """
    forkserver.ensure_running()
    process = context.Process(target=_nothing, daemon=True)
    process.start()
    process.join()
    process.close()
