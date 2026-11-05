"""A pool of worker processes, so that calculations leave the event loop free.

These calculations are short, unlike fits. A worker cannot be interrupted, so a request that times
out gets its answer at once, while its worker stays busy until the calculation ends.
"""

import asyncio
import multiprocessing
from collections.abc import Callable
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, Request

from seeband_api.calc_worker import initialise_worker, warm_up
from seeband_api.errors import ApiError


class CalcPool:
    def __init__(self, workers: int, timeout_s: float) -> None:
        self._workers = workers
        self._timeout_s = timeout_s
        self._executor = self._new_executor()

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

    async def run[**P, T](self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        executor = self._executor
        try:
            future = executor.submit(function, *args, **kwargs)
            return await asyncio.wait_for(asyncio.wrap_future(future), self._timeout_s)
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
        self._executor.shutdown(wait=False, cancel_futures=True)


def _get_calc_pool(request: Request) -> CalcPool:
    pool: CalcPool = request.app.state.calc_pool
    return pool


CalcPoolDep = Annotated[CalcPool, Depends(_get_calc_pool)]
