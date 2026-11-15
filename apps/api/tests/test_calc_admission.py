"""A14: calculations are admitted through a bounded queue, with a few jobs for each client.

Before, one client spending its rate on heavy jobs made another's light calc fail with 504 after
30 s, and aborted requests still ran, 12 of 12.
"""

import asyncio
import logging
import statistics
import time
from typing import Any

import pool_functions
import pytest
from seeband_api.calc_pool import CalcPool
from seeband_api.errors import ApiError

HEAVY_S = 0.3


def _pool(**options: Any) -> CalcPool:
    timeout_s = options.pop("timeout_s", 30.0)
    pool = CalcPool(
        options.pop("workers", 2),
        30.0,
        **{"max_waiting": 8, "max_per_client": 4, "wait_timeout_s": 10.0, **options},
    )
    # Workers start once, so that their start, which can take a second, is not a job's time.
    asyncio.run(_warm(pool))
    pool._timeout_s = timeout_s
    return pool


async def _warm(pool: CalcPool) -> None:
    await asyncio.gather(*(pool.run(pool_functions.double, 1) for _ in range(pool._workers)))


async def _gone() -> bool:
    return True


def _gone_after(seconds: float) -> Any:
    start = time.monotonic()

    async def is_disconnected() -> bool:
        return time.monotonic() - start > seconds

    return is_disconnected


class _Jobs(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.fields: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == "calc_job":
            self.fields.append(record.__dict__["fields"])


@pytest.fixture
def jobs() -> Any:
    handler = _Jobs()
    logger = logging.getLogger("seeband_api")
    logger.addHandler(handler)
    level = logger.level
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(level)


def test_a_flooding_client_is_refused_fast_and_another_stays_fast() -> None:
    pool = _pool()

    async def flood_and_measure() -> tuple[list[Any], list[float], list[float]]:
        refusal_times: list[float] = []

        async def heavy() -> Any:
            started = time.perf_counter()
            try:
                return await pool.run_for("flooder", None, pool_functions.sleep_seconds, HEAVY_S)
            except ApiError as error:
                refusal_times.append(time.perf_counter() - started)
                return error

        # 600 heavy calcs and 60 parses of the largest size, as one address could send them.
        flood = asyncio.gather(*(heavy() for _ in range(660)))
        await asyncio.sleep(0)
        latencies = []
        for value in range(20):
            started = time.perf_counter()
            assert await pool.run_for("other", None, pool_functions.double, value) == 2 * value
            latencies.append(time.perf_counter() - started)
        return await flood, latencies, refusal_times

    try:
        outcomes, latencies, refusal_times = asyncio.run(flood_and_measure())
    finally:
        pool.close()

    refused = [outcome for outcome in outcomes if isinstance(outcome, ApiError)]
    assert len(refused) >= 650
    assert {error.status_code for error in refused} <= {429, 503}
    assert all(error.headers and "Retry-After" in error.headers for error in refused)
    # Refused at once, not after the run's time.
    assert max(refusal_times) < 0.5
    assert statistics.quantiles(latencies, n=20)[-1] < 1.0


def test_aborted_heavy_jobs_do_not_hold_up_the_next_light_one(jobs: _Jobs) -> None:
    # Room for all 12 to wait, so that each is dropped for leaving, not refused for a full queue.
    pool = _pool(max_waiting=16)

    async def abort_then_ask() -> float:
        # 12 clients send a heavy calc each, and leave right away.
        aborted = [
            asyncio.ensure_future(
                pool.run_for(f"c{index}", _gone_after(0.05), pool_functions.sleep_seconds, 1.0)
            )
            for index in range(12)
        ]
        await asyncio.sleep(0.3)
        started = time.perf_counter()
        assert await pool.run_for("next", None, pool_functions.double, 4) == 8
        elapsed = time.perf_counter() - started
        await asyncio.gather(*aborted, return_exceptions=True)
        return elapsed

    try:
        elapsed = asyncio.run(abort_then_ask())
    finally:
        pool.close()

    # Only the two that a worker took at once ran; the light job waited for no more than them.
    assert elapsed < 2 * 1.0
    abandoned = [entry for entry in jobs.fields if entry["abandoned"]]
    assert len(abandoned) == 10
    ran = [entry for entry in jobs.fields if entry["job"] == "sleep_seconds" and "run_ms" in entry]
    assert len(ran) == 2


def test_a_timed_out_job_keeps_its_worker_slot_until_the_worker_is_done() -> None:
    pool = _pool(workers=1, timeout_s=0.2)

    async def time_out_then_ask() -> float:
        with pytest.raises(ApiError) as raised:
            await pool.run(pool_functions.sleep_seconds, 0.8)
        assert raised.value.status_code == 504
        started = time.perf_counter()
        await pool.run(pool_functions.double, 1)
        return time.perf_counter() - started

    try:
        waited = asyncio.run(time_out_then_ask())
    finally:
        pool.close()

    # The light job waited for the worker, rather than queueing in the executor behind it.
    assert 0.4 < waited < 2.0
    assert pool._running == 0


def test_a_full_queue_answers_503_and_a_busy_client_429() -> None:
    pool = _pool(workers=1, max_waiting=1, max_per_client=2)

    async def fill() -> tuple[ApiError, ApiError]:
        first = asyncio.ensure_future(pool.run_for("a", None, pool_functions.sleep_seconds, 0.5))
        second = asyncio.ensure_future(pool.run_for("a", None, pool_functions.double, 1))
        await asyncio.sleep(0.05)
        with pytest.raises(ApiError) as per_client:
            await pool.run_for("a", None, pool_functions.double, 1)
        with pytest.raises(ApiError) as full:
            await pool.run_for("b", None, pool_functions.double, 1)
        await asyncio.gather(first, second)
        return per_client.value, full.value

    try:
        per_client, full = asyncio.run(fill())
    finally:
        pool.close()

    assert (per_client.status_code, per_client.code) == (429, "client_calc_limit")
    assert (full.status_code, full.code) == (503, "calculation_busy")
    assert per_client.headers == full.headers == {"Retry-After": "1"}
    assert pool._per_client == {}


def test_a_job_that_waits_too_long_answers_503_and_leaves_the_queue() -> None:
    pool = _pool(workers=1, wait_timeout_s=0.2)

    async def wait_too_long() -> ApiError:
        running = asyncio.ensure_future(pool.run(pool_functions.sleep_seconds, 0.6))
        await asyncio.sleep(0.05)
        with pytest.raises(ApiError) as raised:
            await pool.run_for("late", None, pool_functions.double, 1)
        await running
        return raised.value

    try:
        error = asyncio.run(wait_too_long())
    finally:
        pool.close()

    assert (error.status_code, error.code) == (503, "calculation_busy")
    assert not pool._waiters
    assert pool._running == 0


def test_a_job_whose_client_left_before_its_turn_never_runs(jobs: _Jobs) -> None:
    pool = _pool(workers=1)

    async def leave() -> None:
        running = asyncio.ensure_future(pool.run(pool_functions.sleep_seconds, 0.3))
        await asyncio.sleep(0.05)
        with pytest.raises(ApiError) as raised:
            await pool.run_for("gone", _gone, pool_functions.sleep_seconds, 5.0)
        assert raised.value.code == "calculation_abandoned"
        await running

    try:
        asyncio.run(leave())
    finally:
        pool.close()

    assert [entry["job"] for entry in jobs.fields if entry["abandoned"]] == ["sleep_seconds"]
    assert all("run_ms" not in entry for entry in jobs.fields if entry["abandoned"])


def test_each_job_logs_its_wait_and_run_and_no_arguments(jobs: _Jobs) -> None:
    pool = _pool(workers=1)
    try:
        asyncio.run(_ask(pool, "secret text"))
    finally:
        pool.close()

    entry = jobs.fields[-1]
    assert entry["job"] == "len"
    assert entry["abandoned"] is False
    assert entry["queue_wait_ms"] >= 0
    assert entry["run_ms"] >= 0
    assert "secret" not in repr(jobs.fields)


async def _ask(pool: CalcPool, text: str) -> int:
    return await pool.run(len, text)


def test_closing_the_pool_ends_a_worker_in_the_middle_of_a_job() -> None:
    pool = _pool(workers=1)
    processes = list(pool._executor._processes.values())

    async def start_and_close() -> None:
        job = asyncio.ensure_future(pool.run(pool_functions.sleep_seconds, 30.0))
        await asyncio.sleep(0.2)
        pool.close()
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)

    asyncio.run(start_and_close())

    assert processes
    assert not any(process.is_alive() for process in processes)
