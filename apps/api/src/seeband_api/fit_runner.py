"""Runs each fit in its own process, which can be killed, as a pool's worker cannot.

A pipe carries events from the process. At most `max_running` fits run at once and `max_waiting`
wait, and a request beyond those is refused at once with a 429. The time limit covers the running
fit, not the wait. The process always ends with the call, however the call ends.
"""

import asyncio
import multiprocessing
from collections.abc import Callable
from http import HTTPStatus
from multiprocessing.connection import Connection
from multiprocessing.context import SpawnProcess
from typing import Annotated, Any

from fastapi import Depends, Request

from seeband_api.calc_worker import initialise_worker
from seeband_api.errors import ApiError
from seeband_api.request_logging import log_calculation_failure

RETRY_AFTER_S = 5
TERMINATE_GRACE_S = 1.0

_context = multiprocessing.get_context("spawn")


def _run_in_child(
    connection: Connection, function: Callable[..., Any], args: tuple[Any, ...]
) -> None:
    """Sends what happens through the pipe. Only an exception's type crosses, not its text."""
    initialise_worker()
    try:
        result = function(*args, lambda update: connection.send(("iteration", update)))
    except BaseException as error:
        connection.send(("error", type(error).__name__))
    else:
        connection.send(("result", result))
    connection.close()


def _stop(process: SpawnProcess) -> None:
    """Terminates a process, then kills it if it does not end."""
    if process.is_alive():
        process.terminate()
        process.join(TERMINATE_GRACE_S)
    if process.is_alive():
        process.kill()
    if process.pid is not None:
        process.join()


class FitRunner:
    def __init__(self, max_running: int, max_waiting: int, timeout_s: float) -> None:
        self._max_waiting = max_waiting
        self._timeout_s = timeout_s
        self._semaphore = asyncio.Semaphore(max_running)
        self._waiting = 0
        self._processes: set[SpawnProcess] = set()

    async def run[T](
        self,
        function: Callable[..., T],
        *args: Any,
        on_iteration: Callable[[Any], None] | None = None,
    ) -> T:
        """Runs `function(*args, send_iteration)` in a new process, and returns its result."""
        if self._semaphore.locked() and self._waiting >= self._max_waiting:
            raise ApiError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "fit_queue_full",
                "Too many fits are running. Try again shortly.",
                headers={"Retry-After": str(RETRY_AFTER_S)},
            )
        self._waiting += 1
        try:
            await self._semaphore.acquire()
        finally:
            self._waiting -= 1
        try:
            result: T = await self._run_in_process(function, args, on_iteration)
            return result
        finally:
            self._semaphore.release()

    async def _run_in_process(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        on_iteration: Callable[[Any], None] | None,
    ) -> Any:
        receiver, sender = _context.Pipe(duplex=False)
        process = _context.Process(target=_run_in_child, args=(sender, function, args), daemon=True)
        self._processes.add(process)
        try:
            # Starting pickles the request into the new process, which takes a moment.
            starting = asyncio.create_task(asyncio.to_thread(process.start))
            await asyncio.shield(starting)
            sender.close()
            async with asyncio.timeout(self._timeout_s):
                return await _read_events(receiver, on_iteration)
        except TimeoutError:
            raise ApiError(
                HTTPStatus.GATEWAY_TIMEOUT, "fit_timeout", "The fit took too long"
            ) from None
        finally:
            await asyncio.shield(self._end(process, receiver, sender))

    async def _end(self, process: SpawnProcess, receiver: Connection, sender: Connection) -> None:
        try:
            await asyncio.to_thread(_stop, process)
        finally:
            sender.close()
            receiver.close()
            self._processes.discard(process)

    def close(self) -> None:
        """Ends every fit, as the server stops."""
        for process in list(self._processes):
            _stop(process)


async def _read_events(receiver: Connection, on_iteration: Callable[[Any], None] | None) -> Any:
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

    def read() -> None:
        try:
            events.put_nowait(receiver.recv())
        except (EOFError, OSError):
            loop.remove_reader(receiver.fileno())
            events.put_nowait(None)

    loop.add_reader(receiver.fileno(), read)
    try:
        while True:
            event = await events.get()
            if event is None:
                raise ApiError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "fit_process_died",
                    "The fit stopped unexpectedly. Try again.",
                )
            kind, value = event
            if kind == "result":
                return value
            if kind == "error":
                log_calculation_failure(value)
                raise ApiError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "fit_failed",
                    "The fit ended with an internal error",
                )
            if on_iteration is not None:
                on_iteration(value)
    finally:
        loop.remove_reader(receiver.fileno())


def _get_fit_runner(request: Request) -> FitRunner:
    runner: FitRunner = request.app.state.fit_runner
    return runner


FitRunnerDep = Annotated[FitRunner, Depends(_get_fit_runner)]
