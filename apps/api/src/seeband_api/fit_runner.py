"""Runs each fit in its own process, which can be killed, as a pool's worker cannot.

A pipe carries events from the process. At most `max_running` fits run at once and `max_waiting`
wait, and a request beyond those is refused at once with a 429. The time limit covers the running
fit, not the wait. The process always ends with the call, however the call ends.
"""

import asyncio
import multiprocessing
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
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


def _run_in_child(job: Connection, events: Connection) -> None:
    """Runs the job from one pipe, and sends what happens through the other.

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


def _stop(process: SpawnProcess) -> None:
    """Terminates a process, then kills it if it does not end."""
    if process.is_alive():
        process.terminate()
        process.join(TERMINATE_GRACE_S)
    if process.is_alive():
        process.kill()
    if process.pid is not None:
        process.join()


@dataclass(eq=False)
class _FitProcess:
    """A process with its pipes, as far as it has started."""

    process: SpawnProcess
    job_reader: Connection
    job_writer: Connection
    events_reader: Connection
    events_writer: Connection
    started: threading.Event = field(default_factory=threading.Event)

    def start_and_send(self, function: Callable[..., Any], args: tuple[Any, ...]) -> None:
        """Runs in a thread, as starting takes a moment, and sending waits for the child to read."""
        try:
            self.process.start()
        finally:
            self.started.set()
        self.job_reader.close()
        self.events_writer.close()
        try:
            self.job_writer.send((function, args))
        except BrokenPipeError:
            pass  # The child has gone, and reading its events reports that.
        self.job_writer.close()

    def stop(self) -> None:
        """Runs in a thread. A call can end while starting, so this waits for a process to stop."""
        self.started.wait()
        _stop(self.process)

    def close_pipes(self) -> None:
        for connection in (
            self.job_reader,
            self.job_writer,
            self.events_reader,
            self.events_writer,
        ):
            connection.close()


class FitRunner:
    def __init__(self, max_running: int, max_waiting: int, timeout_s: float) -> None:
        self._max_waiting = max_waiting
        self._timeout_s = timeout_s
        self._semaphore = asyncio.Semaphore(max_running)
        self._waiting = 0
        self._running: set[_FitProcess] = set()

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
        job_reader, job_writer = _context.Pipe(duplex=False)
        events_reader, events_writer = _context.Pipe(duplex=False)
        process = _context.Process(
            target=_run_in_child, args=(job_reader, events_writer), daemon=True
        )
        fit = _FitProcess(process, job_reader, job_writer, events_reader, events_writer)
        self._running.add(fit)
        launching = asyncio.create_task(asyncio.to_thread(fit.start_and_send, function, args))
        try:
            async with asyncio.timeout(self._timeout_s):
                await asyncio.shield(launching)
                return await _read_events(events_reader, on_iteration)
        except TimeoutError:
            raise ApiError(
                HTTPStatus.GATEWAY_TIMEOUT, "fit_timeout", "The fit took too long"
            ) from None
        finally:
            await _finish_despite_cancellation(self._end(fit, launching))

    async def _end(self, fit: _FitProcess, launching: asyncio.Task[None]) -> None:
        try:
            await asyncio.to_thread(fit.stop)
        finally:
            # With the process gone, the thread has nothing left to wait for.
            await asyncio.wait([launching])
            if not launching.cancelled():
                launching.exception()
            fit.close_pipes()
            self._running.discard(fit)

    def close(self) -> None:
        """Ends the fits still running when the app stops."""
        for fit in list(self._running):
            fit.stop()


async def _finish_despite_cancellation(ending: Coroutine[Any, Any, None]) -> None:
    """Waits for the end even if cancelled again, so that the slot stays held until then."""
    task = asyncio.create_task(ending)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


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
