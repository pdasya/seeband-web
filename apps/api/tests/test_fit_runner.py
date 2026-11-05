"""The runner, with functions that misbehave in their own process."""

import asyncio
import logging
import multiprocessing
import os
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import fit_functions
import pytest
from seeband_api.errors import ApiError
from seeband_api.fit_runner import FitRunner


@pytest.fixture(autouse=True)
def no_fit_process_left() -> Iterator[None]:
    yield
    left = [p for p in multiprocessing.active_children() if "SpawnProcess" in p.name]
    assert left == []


def _run(main: Callable[[], Awaitable[Any]]) -> Any:
    return asyncio.run(main())  # type: ignore[arg-type]


def test_returns_the_result() -> None:
    runner = FitRunner(1, 0, 30.0)

    assert _run(lambda: runner.run(fit_functions.double, 21)) == 42


def test_sends_iterations_while_it_runs() -> None:
    runner = FitRunner(1, 0, 30.0)
    seen: list[int] = []

    result = _run(lambda: runner.run(fit_functions.iterate_then_answer, on_iteration=seen.append))

    assert result == "done"
    assert seen == [1, 2, 3]


def test_fit_past_the_time_limit_answers_504_and_ends() -> None:
    runner = FitRunner(1, 0, 1.5)
    started = time.monotonic()

    with pytest.raises(ApiError) as raised:
        _run(lambda: runner.run(fit_functions.hang))

    assert raised.value.status_code == 504
    assert raised.value.code == "fit_timeout"
    assert time.monotonic() - started < 20


def test_process_that_ignores_terminate_is_killed() -> None:
    # The limit leaves time to start, and the iteration shows that terminate was being ignored.
    runner = FitRunner(1, 0, 5.0)
    seen: list[int] = []
    started = time.monotonic()

    with pytest.raises(ApiError) as raised:
        _run(lambda: runner.run(fit_functions.hang_ignoring_terminate, on_iteration=seen.append))

    assert raised.value.code == "fit_timeout"
    assert seen == [1]
    assert time.monotonic() - started < 20


@pytest.mark.parametrize("function", [fit_functions.die, fit_functions.exit_quietly])
def test_process_that_dies_answers_503(function: Any) -> None:
    runner = FitRunner(1, 0, 30.0)

    with pytest.raises(ApiError) as raised:
        _run(lambda: runner.run(function))

    assert raised.value.status_code == 503
    assert raised.value.code == "fit_process_died"


def test_exception_in_the_process_crosses_as_its_type_only() -> None:
    runner = FitRunner(1, 0, 30.0)
    records: list[logging.LogRecord] = []

    class Recorder(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    recorder = Recorder()
    logger = logging.getLogger("seeband_api")
    logger.addHandler(recorder)
    try:
        with pytest.raises(ApiError) as raised:
            _run(lambda: runner.run(fit_functions.raise_with_a_value, "SECRET-VALUE"))
    finally:
        logger.removeHandler(recorder)

    assert raised.value.status_code == 500
    assert raised.value.code == "fit_failed"
    assert "SECRET-VALUE" not in raised.value.message
    assert raised.value.__cause__ is None
    assert [record.__dict__["fields"] for record in records] == [{"exception_type": "RuntimeError"}]


def test_cancelling_a_call_ends_its_process(tmp_path: Path) -> None:
    runner = FitRunner(1, 0, 60.0)
    pid_file = tmp_path / "pid"

    async def main() -> int:
        task = asyncio.create_task(runner.run(fit_functions.write_pid_and_hang, str(pid_file)))
        while not (pid_file.exists() and pid_file.read_text()):
            await asyncio.sleep(0.02)
        pid = int(pid_file.read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return pid

    pid = asyncio.run(main())

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_requests_beyond_the_limit_are_refused_at_once_with_a_retry_hint() -> None:
    runner = FitRunner(1, 1, 30.0)

    async def main() -> tuple[list[Any], float]:
        running = asyncio.create_task(runner.run(fit_functions.sleep_then_answer, 1.5))
        await asyncio.sleep(0)
        waiting = asyncio.create_task(runner.run(fit_functions.double, 4))
        await asyncio.sleep(0)
        started = time.monotonic()
        with pytest.raises(ApiError) as raised:
            await runner.run(fit_functions.double, 8)
        refused_after = time.monotonic() - started
        assert raised.value.status_code == 429
        assert raised.value.code == "fit_queue_full"
        assert raised.value.headers == {"Retry-After": "5"}
        return [await running, await waiting], refused_after

    results, refused_after = asyncio.run(main())

    assert results == ["woke", 8]
    assert refused_after < 0.5


def test_at_most_the_limit_run_at_once(tmp_path: Path) -> None:
    runner = FitRunner(2, 10, 30.0)
    high_water = 0

    async def main() -> list[int]:
        nonlocal high_water

        async def watch() -> None:
            nonlocal high_water
            while True:
                high_water = max(high_water, len(runner._processes))
                await asyncio.sleep(0.01)

        watcher = asyncio.create_task(watch())
        results = await asyncio.gather(
            *(runner.run(fit_functions.double, value) for value in range(5))
        )
        watcher.cancel()
        return results

    assert asyncio.run(main()) == [0, 2, 4, 6, 8]
    assert high_water == 2


def test_slots_come_back_after_failures() -> None:
    runner = FitRunner(1, 0, 30.0)

    async def main() -> int:
        for _ in range(2):
            with pytest.raises(ApiError):
                await runner.run(fit_functions.die)
        return await runner.run(fit_functions.double, 4)

    assert asyncio.run(main()) == 8


def test_close_ends_running_fits(tmp_path: Path) -> None:
    runner = FitRunner(1, 0, 60.0)
    pid_file = tmp_path / "pid"

    async def main() -> None:
        task = asyncio.create_task(runner.run(fit_functions.write_pid_and_hang, str(pid_file)))
        while not (pid_file.exists() and pid_file.read_text()):
            await asyncio.sleep(0.02)
        pid = int(pid_file.read_text())

        runner.close()

        # Checked at once: the call itself would also end the process on its time limit.
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        with pytest.raises(ApiError) as raised:
            await asyncio.wait_for(task, 5.0)
        assert raised.value.code == "fit_process_died"

    asyncio.run(main())
