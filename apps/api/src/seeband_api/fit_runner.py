"""Runs each fit in its own process, which can be killed, as a pool's worker cannot.

The process is forked from a server that has the core loaded, see `processes`.

A pipe carries events from the process. At most `max_running` fits run at once and `max_waiting`
wait, and a request beyond those is refused at once with a 429. The time limit covers the running
fit, not the wait. The process always ends with its task, however the task ends.
"""

import asyncio
import os
import signal
import threading
import time
from collections import Counter
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from http import HTTPStatus
from multiprocessing.connection import Connection
from multiprocessing.context import ForkServerProcess
from typing import Annotated, Any

from fastapi import Depends, Request

from seeband_api.errors import ApiError
from seeband_api.fit_worker import run_in_child
from seeband_api.processes import context as _context
from seeband_api.request_logging import log_calculation_failure

RETRY_AFTER_S = 5
TERMINATE_GRACE_S = 1.0
FIT_TIMEOUT_MESSAGE = "The fit took too long"
FIT_PROCESS_DIED_MESSAGE = "The fit stopped unexpectedly. Try again."
FIT_FAILED_MESSAGE = "The fit ended with an internal error"


def _stop(process: ForkServerProcess) -> None:
    """Terminates a process, then kills it if it does not end."""
    if process.is_alive():
        process.terminate()
        process.join(TERMINATE_GRACE_S)
    if process.is_alive():
        process.kill()
    if process.pid is not None:
        process.join()
        if process.exitcode == _FORK_SERVER_LOST:
            _end_orphan(process.pid)


# The exit code that multiprocessing gives a child whose fork server has gone, which is where the
# real one would have come from. Such a child can still be running, now a child of PID 1, and
# `is_alive`, `terminate` and `kill` all take it for ended.
_FORK_SERVER_LOST = 255


def _end_orphan(pid: int) -> None:
    """Terminates, then kills, a child that multiprocessing has lost track of.

    The pid is its own until something reaps it, and nothing does before the fork server has gone,
    so the signals cannot reach another process. Only a fit that itself exits with 255 gets here
    with its pid already free, and the run_in_child of a fit does not.
    """
    deadline = time.monotonic() + TERMINATE_GRACE_S
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.01)
        deadline = time.monotonic() + TERMINATE_GRACE_S


@dataclass(eq=False)
class _FitProcess:
    """A process with its pipes, as far as it has started."""

    process: ForkServerProcess
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

    def release(self) -> None:
        """Closes what the fit holds open now, rather than whenever garbage collection runs."""
        for connection in (
            self.job_reader,
            self.job_writer,
            self.events_reader,
            self.events_writer,
        ):
            connection.close()
        self.process.close()


class FitRunner:
    def __init__(
        self,
        max_running: int,
        max_waiting: int,
        timeout_s: float,
        max_per_client: int | None = None,
    ) -> None:
        self._max_admitted = max_running + max_waiting
        self._max_per_client = max_per_client
        self._by_client: Counter[str] = Counter()
        self._timeout_s = timeout_s
        self._semaphore = asyncio.Semaphore(max_running)
        self._admitted = 0
        self._running: set[_FitProcess] = set()

    def submit[T](
        self,
        function: Callable[..., T],
        *args: Any,
        client: str | None = None,
        on_started: Callable[[], None] | None = None,
        on_iteration: Callable[[Any], None] | None = None,
    ) -> asyncio.Task[T]:
        """Takes a place at once, or refuses, and returns a task that runs the fit.

        The task runs `function(*args, send_iteration)` in a new process. `on_started` is called
        when the fit stops waiting. Cancelling the task ends the fit, and ends once its process has.
        `client` says whose place this is, for the limit per client.
        """
        if self._admitted >= self._max_admitted:
            raise ApiError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "fit_queue_full",
                "Too many fits are running. Try again shortly.",
                headers={"Retry-After": str(RETRY_AFTER_S)},
            )
        if (
            client is not None
            and self._max_per_client is not None
            and self._by_client[client] >= self._max_per_client
        ):
            raise ApiError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "client_fit_limit",
                "This client has too many fits running or waiting",
                headers={"Retry-After": str(RETRY_AFTER_S)},
            )
        self._admitted += 1
        if client is not None:
            self._by_client[client] += 1
        task = asyncio.create_task(self._wait_and_run(function, args, on_started, on_iteration))
        # A callback, as a task cancelled before its first step never runs its body.
        task.add_done_callback(lambda finished: self._leave(finished, client))
        return task

    async def run[T](
        self,
        function: Callable[..., T],
        *args: Any,
        on_iteration: Callable[[Any], None] | None = None,
    ) -> T:
        """Submits a fit and waits for its result. Cancelling this cancels the fit."""
        return await self.submit(function, *args, on_iteration=on_iteration)

    def _leave(self, task: asyncio.Task[Any], client: str | None) -> None:
        self._admitted -= 1
        if client is not None:
            self._by_client[client] -= 1
            if not self._by_client[client]:
                del self._by_client[client]
        # Marks the exception as retrieved. A client that has gone never reads it, and asyncio
        # would otherwise print it with its traceback.
        if not task.cancelled():
            task.exception()

    async def _wait_and_run(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        on_started: Callable[[], None] | None,
        on_iteration: Callable[[Any], None] | None,
    ) -> Any:
        async with self._semaphore:
            if on_started is not None:
                on_started()
            return await self._run_in_process(function, args, on_iteration)

    async def _run_in_process(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        on_iteration: Callable[[Any], None] | None,
    ) -> Any:
        job_reader, job_writer = _context.Pipe(duplex=False)
        events_reader, events_writer = _context.Pipe(duplex=False)
        process = _context.Process(
            target=run_in_child, args=(job_reader, events_writer), daemon=True
        )
        fit = _FitProcess(process, job_reader, job_writer, events_reader, events_writer)
        self._running.add(fit)
        launching = asyncio.create_task(asyncio.to_thread(fit.start_and_send, function, args))
        try:
            async with asyncio.timeout(self._timeout_s):
                await asyncio.shield(launching)
                return await _read_events(events_reader, on_iteration)
        except TimeoutError:
            raise ApiError(HTTPStatus.GATEWAY_TIMEOUT, "fit_timeout", FIT_TIMEOUT_MESSAGE) from None
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
            self._running.discard(fit)
            fit.release()

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
                    FIT_PROCESS_DIED_MESSAGE,
                )
            kind, value = event
            if kind == "result":
                return value
            if kind == "error":
                log_calculation_failure(value)
                raise ApiError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "fit_failed",
                    FIT_FAILED_MESSAGE,
                )
            if on_iteration is not None:
                on_iteration(value)
    finally:
        loop.remove_reader(receiver.fileno())


def _get_fit_runner(request: Request) -> FitRunner:
    runner: FitRunner = request.app.state.fit_runner
    return runner


FitRunnerDep = Annotated[FitRunner, Depends(_get_fit_runner)]
