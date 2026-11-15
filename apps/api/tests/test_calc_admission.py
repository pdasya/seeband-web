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
    """A client keeps sending heavy jobs for 3 s from many loops; another's light jobs still run
    on the worker that the flooder cannot take."""
    pool = _pool()

    async def flood_and_measure() -> tuple[int, int, list[float], list[float]]:
        refusal_times: list[float] = []
        done = 0
        stop = asyncio.Event()

        async def heavy_loop() -> None:
            nonlocal done
            while not stop.is_set():
                started = time.perf_counter()
                try:
                    await pool.run_for("flooder", None, pool_functions.sleep_seconds, HEAVY_S)
                    done += 1
                except ApiError:
                    refusal_times.append(time.perf_counter() - started)
                    await asyncio.sleep(0.01)

        loops = [asyncio.ensure_future(heavy_loop()) for _ in range(20)]
        await asyncio.sleep(0.2)
        latencies = []
        deadline = time.monotonic() + 3
        value = 0
        while time.monotonic() < deadline:
            started = time.perf_counter()
            assert await pool.run_for("other", None, pool_functions.double, value) == 2 * value
            latencies.append(time.perf_counter() - started)
            value += 1
            await asyncio.sleep(0.05)
        stop.set()
        await asyncio.gather(*loops)
        return done, len(refusal_times), latencies, refusal_times

    try:
        done, refused, latencies, refusal_times = asyncio.run(flood_and_measure())
    finally:
        pool.close()

    assert done > 0 and refused > 100
    # Refused at once, not after the run's time.
    assert statistics.quantiles(refusal_times, n=20)[-1] < 0.2
    assert len(latencies) > 20
    # The flooder runs on one worker at most, so the other is free for these.
    assert statistics.quantiles(latencies, n=20)[-1] < 0.5


def test_a_client_runs_one_job_fewer_than_the_workers_at_once() -> None:
    pool = _pool(workers=3)
    running: list[int] = []

    async def heavy_burst() -> None:
        jobs = [
            asyncio.ensure_future(pool.run_for("a", None, pool_functions.sleep_seconds, 0.3))
            for _ in range(4)
        ]
        await asyncio.sleep(0.1)
        running.append(pool._running)
        await asyncio.gather(*jobs)

    try:
        asyncio.run(heavy_burst())
    finally:
        pool.close()

    assert running == [2]


def test_free_slots_go_round_the_clients_in_turn() -> None:
    pool = _pool(workers=1, max_running_per_client=1)
    order: list[str] = []

    async def queue_up() -> None:
        async def job(client: str) -> None:
            await pool.run_for(client, None, pool_functions.sleep_seconds, 0.05)
            order.append(client)

        jobs = [asyncio.ensure_future(job("a")) for _ in range(3)]
        await asyncio.sleep(0.01)
        jobs += [asyncio.ensure_future(job("b")) for _ in range(2)]
        await asyncio.gather(*jobs)

    try:
        asyncio.run(queue_up())
    finally:
        pool.close()

    # The first a ran at once; then b's jobs take every other turn, though a's came first.
    assert order == ["a", "b", "a", "b", "a"]


def test_a_worker_that_dies_after_its_504_does_not_break_the_pool() -> None:
    """Nobody waits for a job after its 504, so the pool must heal itself when its worker dies."""
    pool = _pool(workers=1, timeout_s=0.2)

    async def die_after_504() -> list[Any]:
        with pytest.raises(ApiError) as raised:
            await pool.run(pool_functions.sleep_then_die, 0.3)
        assert raised.value.status_code == 504
        await asyncio.sleep(0.6)
        pool._timeout_s = 30.0
        answers: list[Any] = []
        for _ in range(3):
            try:
                answers.append(await pool.run(pool_functions.double, 2))
            except ApiError as error:
                answers.append(error.code)
        return answers

    try:
        answers = asyncio.run(die_after_504())
    finally:
        pool.close()

    # At most one 503 while new workers start, then answers.
    assert answers[-1] == 4
    assert answers.count("calculation_unavailable") <= 1
    assert pool._running == 0


def test_a_stuck_job_has_its_workers_replaced() -> None:
    pool = _pool(workers=1, timeout_s=0.2)

    async def stuck_then_ask() -> float:
        with pytest.raises(ApiError):
            await pool.run(pool_functions.sleep_seconds, 30.0)
        pool._timeout_s = 30.0
        started = time.perf_counter()
        await pool.run(pool_functions.double, 2)
        return time.perf_counter() - started

    try:
        waited = asyncio.run(stuck_then_ask())
    finally:
        pool.close()

    # Not the 30 s of the stuck job: its worker ended at twice the run time, and a new one started.
    assert waited < 10


def test_a_cancel_at_the_front_of_the_queue_leaks_no_slot() -> None:
    pool = _pool(workers=1)

    async def cancel_while_checking() -> None:
        checking = asyncio.Event()

        async def is_disconnected() -> bool:
            checking.set()
            await asyncio.sleep(10)
            return False

        job = asyncio.ensure_future(pool.run_for("c", is_disconnected, pool_functions.double, 1))
        await checking.wait()
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        assert await pool.run(pool_functions.double, 3) == 6

    try:
        asyncio.run(cancel_while_checking())
    finally:
        pool.close()

    assert pool._running == 0
    assert pool._per_client == {}


def test_aborted_heavy_jobs_do_not_hold_up_the_next_light_one(jobs: _Jobs) -> None:
    # The default queue of 8, which the 12 overfill.
    pool = _pool()

    async def abort_then_ask() -> float:
        # 12 clients send a heavy calc each, and leave right away.
        aborted = [
            asyncio.ensure_future(
                pool.run_for(f"c{index}", _gone_after(0.05), pool_functions.sleep_seconds, 1.0)
            )
            for index in range(12)
        ]
        # Right after they left, while their jobs may still fill the queue for one poll.
        await asyncio.sleep(0.06)
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
    assert len(abandoned) >= 8
    ran = [entry for entry in jobs.fields if entry["job"] == "sleep_seconds" and "run_ms" in entry]
    assert len(ran) == 2


def test_a_timed_out_job_keeps_its_worker_slot_until_the_worker_is_done() -> None:
    pool = _pool(workers=1, timeout_s=0.2)

    async def time_out_then_ask() -> float:
        # Past its time, but not so far past that it counts as stuck.
        with pytest.raises(ApiError) as raised:
            await pool.run(pool_functions.sleep_seconds, 0.35)
        assert raised.value.status_code == 504
        started = time.perf_counter()
        await pool.run(pool_functions.double, 1)
        return time.perf_counter() - started

    try:
        waited = asyncio.run(time_out_then_ask())
    finally:
        pool.close()

    # The light job waited for the worker, rather than queueing in the executor behind it.
    assert 0.1 < waited < 1.5
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
    for error in (per_client, full):
        assert error.headers is not None
        assert int(error.headers["Retry-After"]) >= 1
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
    assert pool._waiting == 0
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
