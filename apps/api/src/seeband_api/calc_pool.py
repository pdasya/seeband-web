"""A pool of worker processes, so that calculations leave the event loop free, and a queue to it.

These calculations are short, unlike fits. A worker cannot be interrupted, so a request that times
out gets its answer at once, while its worker stays busy until the calculation ends.

Jobs are admitted through a queue in the API rather than straight to the executor:

- It holds exactly one slot for each worker. A slot stays taken until its worker has finished, also
  after a 504, so the executor never holds a backlog. A job still running at twice its time is
  taken as stuck, and the workers are replaced.
- Free slots go to waiting clients in turn, one job each, not to whoever came first, and one client
  can run at most `max_running_per_client` jobs at once, by default one fewer than the workers. So
  a client sending heavy jobs without pause always leaves a worker for others.
- Past the slots, a bounded list of jobs waits, each for a limited time. A job whose client has gone
  is dropped before it runs. Each client can have a few jobs admitted at once.
- A full list or a client over its count gets a fast answer with `Retry-After`.
- A worker that dies breaks the executor, which is then replaced, also when no request is waiting
  for that worker any more. The jobs it was running fail with it.
- New workers fork from a server with the core loaded, and get no job until each has answered a
  warm-up, at start and after a replacement.
"""

import asyncio
import logging
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import BrokenExecutor, Future, ProcessPoolExecutor
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, Request

from seeband_api.calc_worker import initialise_worker, warm_up
from seeband_api.errors import ApiError
from seeband_api.processes import context as process_context
from seeband_api.request_limits import client_key

_logger = logging.getLogger("seeband_api")

# How often a waiting job checks whether its client is still there, and how long a full queue waits
# for such jobs to leave before it refuses a new one.
_DISCONNECT_POLL_S = 0.1
# Bounds of the `Retry-After` that a busy pool suggests, from the jobs ahead and their usual time.
_MIN_RETRY_AFTER_S = 1
_MAX_RETRY_AFTER_S = 30
# How fast the usual run time follows new runs.
_RUN_TIME_WEIGHT = 0.2
# A job still running after this many times its run time is stuck, and its workers are replaced.
_STUCK_AFTER_RUN_TIMES = 2
# What nginx calls a request whose client closed it. Nobody reads it, and it keeps such requests
# apart from real overload in the logs.
_CLIENT_CLOSED_REQUEST = 499


class _ClientGone(Exception):
    """A waiting job's client has gone."""


@dataclass
class _Waiter:
    turn: asyncio.Future[None]
    client: str


@dataclass
class _Client:
    """One client's jobs: waiting in turn, running, and admitted in all."""

    waiting: deque[_Waiter] = field(default_factory=deque)
    running: int = 0
    admitted: int = 0
    # When it last got a slot, so that the one served longest ago goes next. A new client first.
    last_turn: int = -1


class CalcPool:
    def __init__(
        self,
        workers: int,
        timeout_s: float,
        max_waiting: int = 8,
        max_per_client: int = 4,
        wait_timeout_s: float = 10.0,
        max_running_per_client: int | None = None,
    ) -> None:
        self._workers = workers
        self._timeout_s = timeout_s
        self._max_waiting = max_waiting
        self._max_per_client = max_per_client
        self._wait_timeout_s = wait_timeout_s
        self._max_running_per_client = max_running_per_client or max(1, workers - 1)
        self._executor = self._new_executor()
        # Slots taken by jobs that a worker holds or is about to, until the worker is done.
        self._running = 0
        self._waiting = 0
        # Clients with jobs, and a count of the slots given, by which they take turns.
        self._clients: dict[str, _Client] = {}
        self._turns = 0
        self._mean_run_s = 1.0
        # Warm-up jobs of new workers that have not answered yet. No slot is given out until they
        # have, so a job does not wait in the executor for a worker to start, with its time running.
        self._warming: list[Future[None]] = []

    @property
    def _per_client(self) -> dict[str, int]:
        """Jobs admitted for each client, waiting or running."""
        return {name: client.admitted for name, client in self._clients.items()}

    def _new_executor(self) -> ProcessPoolExecutor:
        # Workers fork from a server with the core loaded, so new ones start in milliseconds.
        return ProcessPoolExecutor(
            max_workers=self._workers,
            mp_context=process_context,
            initializer=initialise_worker,
        )

    def warm_up(self) -> None:
        """Starts every worker, and gives out no slot until each warm-up job has answered.

        Called at start and for each replaced executor.
        """
        futures = [self._executor.submit(warm_up) for _ in range(self._workers)]
        # Only the latest warm-up holds the slots, not that of an executor since replaced.
        self._warming = futures
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # Nobody waits yet. The first job's dispatch checks the warm-up itself.

        def answered_from_worker_thread(_: Future[None]) -> None:
            try:
                loop.call_soon_threadsafe(self._dispatch)
            except RuntimeError:
                pass  # That loop has closed. The next dispatch checks the warm-up itself.

        for future in futures:
            future.add_done_callback(answered_from_worker_thread)

    async def run[**P, T](
        self,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Runs a job for no client in particular, as a test or a single caller does."""
        return await self.run_for("", None, function, *args, **kwargs)

    async def run_for[**P, T](
        self,
        client: str,
        is_disconnected: Callable[[], Awaitable[bool]] | None,
        function: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Runs a job for a client once a slot is its, and refuses it at once if it cannot wait."""
        await self._admit(client)
        queued = time.monotonic()
        try:
            started = await self._take_slot(client, is_disconnected)
        except _ClientGone:
            self._leave(client)
            _log_job(function, (time.monotonic() - queued) * 1000, None, abandoned=True)
            raise _abandoned() from None
        except BaseException:
            self._leave(client)
            raise
        wait_ms = (started - queued) * 1000
        try:
            gone = is_disconnected is not None and await is_disconnected()
        except BaseException:
            self._finish(client)
            self._leave(client)
            raise
        if gone:
            # The client left while its job reached a slot, so it never reaches a worker.
            self._finish(client)
            self._leave(client)
            _log_job(function, wait_ms, None, abandoned=True)
            raise _abandoned()
        return await self._run_in_slot(client, function, args, kwargs, wait_ms)

    async def _admit(self, client: str) -> None:
        state = self._clients.get(client)
        if state is not None and state.admitted >= self._max_per_client:
            raise ApiError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "client_calc_limit",
                f"At most {self._max_per_client} calculations of one client at once",
                headers={"Retry-After": str(self._retry_after_s())},
            )
        if self._waiting >= self._max_waiting:
            # Jobs whose clients have gone leave within a poll, so they do not keep this one out.
            await asyncio.sleep(_DISCONNECT_POLL_S)
            if self._waiting >= self._max_waiting:
                raise self._busy()
        self._clients.setdefault(client, _Client()).admitted += 1

    def _leave(self, client: str) -> None:
        state = self._clients.get(client)
        if state is None:
            return
        state.admitted -= 1
        if state.admitted <= 0 and not state.waiting and state.running <= 0:
            del self._clients[client]

    async def _take_slot(
        self, client: str, is_disconnected: Callable[[], Awaitable[bool]] | None
    ) -> float:
        """Waits for a slot that is this job's turn, and returns when it got it."""
        waiter = _Waiter(asyncio.get_running_loop().create_future(), client)
        self._clients[client].waiting.append(waiter)
        self._waiting += 1
        self._dispatch()
        deadline = time.monotonic() + self._wait_timeout_s
        try:
            while not waiter.turn.done():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._busy()
                await asyncio.wait({waiter.turn}, timeout=min(_DISCONNECT_POLL_S, remaining))
                # A warm-up that answered to another event loop, as a test's, is seen here.
                self._dispatch()
                # A turn that came while this waited counts, whatever else happened since.
                if not waiter.turn.done() and is_disconnected is not None:
                    if await is_disconnected() and not waiter.turn.done():
                        raise _ClientGone
            return time.monotonic()
        except BaseException:
            if waiter.turn.done() and not waiter.turn.cancelled():
                # The slot came as it gave up, so it passes to the next in turn.
                self._finish(client)
            else:
                waiter.turn.cancel()
                self._clients[client].waiting.remove(waiter)
                self._waiting -= 1
            raise

    def _dispatch(self) -> None:
        """Gives free slots to waiting clients in turn, one job each, within each one's cap."""
        if not all(future.done() for future in self._warming):
            return
        while self._running < self._workers:
            eligible = [
                state
                for state in self._clients.values()
                if state.waiting and state.running < self._max_running_per_client
            ]
            if not eligible:
                return
            # The client served longest ago goes next, so each waiting client gets a job in turn.
            state = min(eligible, key=lambda candidate: candidate.last_turn)
            waiter = state.waiting.popleft()
            self._waiting -= 1
            state.running += 1
            self._running += 1
            self._turns += 1
            state.last_turn = self._turns
            waiter.turn.set_result(None)

    def _finish(self, client: str) -> None:
        """Frees a job's slot, and gives it to the next client in turn."""
        self._running -= 1
        state = self._clients.get(client)
        if state is not None:
            state.running -= 1
        self._dispatch()

    async def _run_in_slot[T](
        self,
        client: str,
        function: Callable[..., T],
        args: tuple[object, ...],
        kwargs: dict[str, object],
        wait_ms: float,
    ) -> T:
        loop = asyncio.get_running_loop()
        executor = self._executor
        started = time.monotonic()
        try:
            future: Future[T] = executor.submit(function, *args, **kwargs)
        except BrokenExecutor as error:
            # A worker died with no request watching, so this one finds the pool broken.
            self._finish(client)
            self._leave(client)
            self._replace(executor)
            raise _unavailable() from error
        except BaseException:
            self._finish(client)
            self._leave(client)
            raise

        freed = False
        timed_out = False

        def free() -> None:
            nonlocal freed
            if freed:
                return
            freed = True
            run_s = time.monotonic() - started
            if not timed_out:
                self._mean_run_s += _RUN_TIME_WEIGHT * (run_s - self._mean_run_s)
            if not future.cancelled() and isinstance(future.exception(), BrokenExecutor):
                # A worker died; the next job gets new ones, whoever was watching this one.
                self._replace(executor)
            self._finish(client)
            self._leave(client)
            _log_job(function, wait_ms, run_s * 1000, abandoned=False, timed_out=timed_out)

        def free_from_worker_thread(_: Future[T]) -> None:
            try:
                loop.call_soon_threadsafe(free)
            except RuntimeError:
                pass  # The loop has closed, and the pool with it.

        try:
            try:
                return await asyncio.wait_for(asyncio.wrap_future(future), self._timeout_s)
            finally:
                # The slot is free only once the worker is. After a timeout or a cancelled request
                # the worker goes on, so its slot waits for it, and the executor never holds a
                # backlog.
                if future.done():
                    free()
                else:
                    future.add_done_callback(free_from_worker_thread)
        except BrokenExecutor as error:
            # A worker died, which breaks the pool for good, so the next request gets a new one.
            self._replace(executor)
            raise _unavailable() from error
        except TimeoutError as error:
            timed_out = True
            loop.call_later(
                self._timeout_s * (_STUCK_AFTER_RUN_TIMES - 1),
                self._replace_if_stuck,
                future,
                executor,
            )
            raise ApiError(
                HTTPStatus.GATEWAY_TIMEOUT, "calculation_timeout", "The calculation took too long"
            ) from error

    def _replace_if_stuck[T](self, future: Future[T], executor: ProcessPoolExecutor) -> None:
        """Ends the workers of a job that runs far past its time, as nothing else would free them.

        Other jobs on those workers end too, as a 503, and their slots are freed as they end.
        """
        if not future.done() and self._executor is executor:
            _logger.warning("calc_job_stuck", extra={"fields": {"timeout_s": self._timeout_s}})
            self._replace(executor)
            _terminate(executor)

    def _replace(self, executor: ProcessPoolExecutor) -> None:
        """Gives the pool new workers in place of a broken executor, once."""
        if self._executor is executor:
            self._executor = self._new_executor()
            self.warm_up()

    def _retry_after_s(self) -> int:
        """About when a slot will be free: the jobs ahead, shared by the workers, at their usual
        time."""
        ahead = (self._waiting / self._workers + 1) * self._mean_run_s
        return min(_MAX_RETRY_AFTER_S, max(_MIN_RETRY_AFTER_S, math.ceil(ahead)))

    def _busy(self) -> ApiError:
        return ApiError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "calculation_busy",
            "Too many calculations are waiting. Try again shortly.",
            headers={"Retry-After": str(self._retry_after_s())},
        )

    def close(self) -> None:
        """Stops the workers, also any in the middle of a job, so that none outlives the server."""
        _terminate(self._executor)


def _terminate(executor: ProcessPoolExecutor) -> None:
    # The executor's processes, which `shutdown` alone leaves running to the end of their job.
    processes = list((executor._processes or {}).values())
    executor.shutdown(wait=False, cancel_futures=True)
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=5)


def _unavailable() -> ApiError:
    return ApiError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "calculation_unavailable",
        "The calculation stopped unexpectedly. Try again.",
    )


def _abandoned() -> ApiError:
    # Nobody reads this answer, as the client has gone.
    return ApiError(_CLIENT_CLOSED_REQUEST, "calculation_abandoned", "The client went away")


def _log_job(
    function: Callable[..., object],
    wait_ms: float,
    run_ms: float | None,
    *,
    abandoned: bool,
    timed_out: bool = False,
) -> None:
    """One line for a job: what ran, how long it waited and ran. Never its arguments."""
    fields: dict[str, object] = {
        "job": getattr(function, "__name__", "unknown"),
        "queue_wait_ms": round(wait_ms, 1),
        "abandoned": abandoned,
        "timed_out": timed_out,
    }
    if run_ms is not None:
        fields["run_ms"] = round(run_ms, 1)
    _logger.info("calc_job", extra={"fields": fields})


@dataclass(frozen=True)
class ClientPool:
    """The pool as one request uses it: its jobs count for its client, and stop if it leaves."""

    pool: CalcPool
    client: str
    is_disconnected: Callable[[], Awaitable[bool]]

    async def run[**P, T](self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        return await self.pool.run_for(self.client, self.is_disconnected, function, *args, **kwargs)


def _get_calc_pool(request: Request) -> ClientPool:
    pool: CalcPool = request.app.state.calc_pool
    return ClientPool(pool, client_key(request.scope), request.is_disconnected)


CalcPoolDep = Annotated[ClientPool, Depends(_get_calc_pool)]
