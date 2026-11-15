"""A pool of worker processes, so that calculations leave the event loop free, and a queue to it.

These calculations are short, unlike fits. A worker cannot be interrupted, so a request that times
out gets its answer at once, while its worker stays busy until the calculation ends.

Jobs are admitted through a queue in the API rather than straight to the executor. It holds exactly
one slot for each worker, and a slot stays taken until its worker has finished, also after a 504,
so the executor never holds a backlog. Past the slots, a bounded list of jobs waits in turn, each
for a limited time, and a job whose client has gone is dropped before it runs. Each client can
have a few jobs admitted at once. A full list or a client over its count gets a fast answer with
`Retry-After`, so one client spending its rate on heavy jobs cannot make another's light job wait
for long.
"""

import asyncio
import logging
import multiprocessing
import time
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import BrokenExecutor, Future, ProcessPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, Request

from seeband_api.calc_worker import initialise_worker, warm_up
from seeband_api.errors import ApiError
from seeband_api.request_limits import client_key

_logger = logging.getLogger("seeband_api")

# How often a waiting job checks whether its client is still there.
_DISCONNECT_POLL_S = 0.1
# A free slot comes within a job's time, so a client may try again about that soon.
_RETRY_AFTER_S = 1


class _ClientGone(Exception):
    """A waiting job's client has gone."""


@dataclass
class _Waiter:
    turn: asyncio.Future[None]
    client: str


class CalcPool:
    def __init__(
        self,
        workers: int,
        timeout_s: float,
        max_waiting: int = 8,
        max_per_client: int = 4,
        wait_timeout_s: float = 10.0,
    ) -> None:
        self._workers = workers
        self._timeout_s = timeout_s
        self._max_waiting = max_waiting
        self._max_per_client = max_per_client
        self._wait_timeout_s = wait_timeout_s
        self._executor = self._new_executor()
        # Slots taken by jobs that a worker holds or is about to, until the worker is done.
        self._running = 0
        self._waiters: deque[_Waiter] = deque()
        # Jobs of each client, waiting or running, until their worker is done.
        self._per_client: dict[str, int] = {}

    def _new_executor(self) -> ProcessPoolExecutor:
        # The server has threads, which `fork` does not copy safely.
        return ProcessPoolExecutor(
            max_workers=self._workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=initialise_worker,
        )

    def warm_up(self) -> None:
        for _ in range(self._workers):
            self._executor.submit(warm_up)

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
        """Runs a job for a client once a slot is free, and refuses it at once if it cannot wait."""
        self._admit(client)
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
        if is_disconnected is not None and await is_disconnected():
            # The client left while its job reached the front, so it never reaches a worker.
            self._release()
            self._leave(client)
            _log_job(function, wait_ms, None, abandoned=True)
            raise _abandoned()
        return await self._run_in_slot(client, function, args, kwargs, wait_ms)

    def _admit(self, client: str) -> None:
        if self._per_client.get(client, 0) >= self._max_per_client:
            raise ApiError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "client_calc_limit",
                f"At most {self._max_per_client} calculations of one client at once",
                headers={"Retry-After": str(_RETRY_AFTER_S)},
            )
        if self._running >= self._workers and len(self._waiters) >= self._max_waiting:
            raise _busy()
        self._per_client[client] = self._per_client.get(client, 0) + 1

    def _leave(self, client: str) -> None:
        count = self._per_client.get(client, 0) - 1
        if count > 0:
            self._per_client[client] = count
        else:
            self._per_client.pop(client, None)

    async def _take_slot(
        self, client: str, is_disconnected: Callable[[], Awaitable[bool]] | None
    ) -> float:
        """Waits for a free slot in turn, and returns when the job got it."""
        if self._running < self._workers and not self._waiters:
            self._running += 1
            return time.monotonic()
        waiter = _Waiter(asyncio.get_running_loop().create_future(), client)
        self._waiters.append(waiter)
        deadline = time.monotonic() + self._wait_timeout_s
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _busy()
                done, _ = await asyncio.wait(
                    {waiter.turn}, timeout=min(_DISCONNECT_POLL_S, remaining)
                )
                if done:
                    return time.monotonic()
                if is_disconnected is not None and await is_disconnected():
                    raise _ClientGone
        except BaseException:
            if waiter.turn.done() and not waiter.turn.cancelled():
                # The slot came as it gave up, so it passes to the next in turn.
                self._release()
            else:
                waiter.turn.cancel()
                self._waiters.remove(waiter)
            raise

    def _release(self) -> None:
        """Gives a finished job's slot to the next job in turn, or frees it."""
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.turn.done():
                waiter.turn.set_result(None)
                return
        self._running -= 1

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
        except BaseException:
            self._release()
            self._leave(client)
            raise

        freed = False

        def free() -> None:
            nonlocal freed
            if not freed:
                freed = True
                self._release()
                self._leave(client)
                _log_job(function, wait_ms, (time.monotonic() - started) * 1000, abandoned=False)

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
            if self._executor is executor:
                self._executor = self._new_executor()
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "calculation_unavailable",
                "The calculation stopped unexpectedly. Try again.",
            ) from error
        except TimeoutError as error:
            raise ApiError(
                HTTPStatus.GATEWAY_TIMEOUT, "calculation_timeout", "The calculation took too long"
            ) from error

    def close(self) -> None:
        """Stops the workers, also any in the middle of a job, so that none outlives the server."""
        processes = list((self._executor._processes or {}).values())
        self._executor.shutdown(wait=False, cancel_futures=True)
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)


def _busy() -> ApiError:
    return ApiError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "calculation_busy",
        "Too many calculations are waiting. Try again shortly.",
        headers={"Retry-After": str(_RETRY_AFTER_S)},
    )


def _abandoned() -> ApiError:
    # Nobody reads this answer, as the client has gone.
    return ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "calculation_abandoned", "The client went away")


def _log_job(
    function: Callable[..., object],
    wait_ms: float,
    run_ms: float | None,
    *,
    abandoned: bool,
) -> None:
    """One line for a job: what ran, how long it waited and ran. Never its arguments."""
    fields: dict[str, object] = {
        "job": getattr(function, "__name__", "unknown"),
        "queue_wait_ms": round(wait_ms, 1),
        "abandoned": abandoned,
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
