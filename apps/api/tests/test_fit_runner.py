"""The runner, with functions that misbehave in their own process."""

import asyncio
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
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
    runner = FitRunner(1, 0, 60.0)

    async def main() -> None:
        seen = asyncio.Event()
        task = asyncio.create_task(
            runner.run(fit_functions.hang_ignoring_terminate, on_iteration=lambda _: seen.set())
        )
        # The iteration shows that it has started to ignore terminate.
        await seen.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10.0)

    asyncio.run(main())


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


@pytest.mark.parametrize("delay_s", [0.0, 0.02, 0.1, 0.3])
@pytest.mark.parametrize("size", [2_000, 128_000, 2_000_000])
def test_cancelling_while_it_starts_leaves_no_process(delay_s: float, size: int) -> None:
    """A large request waits for the child to read it, which is when a cancel used to leak."""
    runner = FitRunner(1, 0, 60.0)

    async def main() -> None:
        task = asyncio.create_task(runner.run(fit_functions.hang_with_a_large_request, b"x" * size))
        await asyncio.sleep(delay_s)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10.0)
        assert not runner._semaphore.locked()
        assert runner._running == set()

    asyncio.run(main())


def test_a_second_cancel_keeps_the_slot_until_the_process_has_ended() -> None:
    runner = FitRunner(1, 0, 60.0)

    async def main() -> None:
        seen = asyncio.Event()
        task = asyncio.create_task(
            runner.run(fit_functions.hang_ignoring_terminate, on_iteration=lambda _: seen.set())
        )
        await seen.wait()
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10.0)
        alive = [
            child
            for child in multiprocessing.active_children()
            if "SpawnProcess" in child.name and child.is_alive()
        ]
        assert alive == []

    asyncio.run(main())


def test_exit_in_the_process_answers_500_with_its_type_only() -> None:
    runner = FitRunner(1, 0, 30.0)

    with pytest.raises(ApiError) as raised:
        _run(lambda: runner.run(fit_functions.exit_with_a_value, "SECRET-VALUE"))

    assert raised.value.code == "fit_failed"


def test_pipes_are_closed_however_a_fit_ends() -> None:
    runner = FitRunner(1, 0, 30.0)

    async def main() -> None:
        await runner.run(fit_functions.double, 2)
        before = len(os.listdir("/dev/fd"))
        for _ in range(3):
            await runner.run(fit_functions.double, 2)
            with pytest.raises(ApiError):
                await runner.run(fit_functions.die)
        assert len(os.listdir("/dev/fd")) <= before

    asyncio.run(main())


def test_fit_ends_when_the_server_is_killed(tmp_path: Path, support_dir: Path) -> None:
    pid_file = tmp_path / "pid"
    server = subprocess.run(
        [sys.executable, str(support_dir / "run_fit_then_die.py"), str(pid_file)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    assert server.returncode == -signal.SIGKILL, server.stderr
    pid = int(pid_file.read_text())

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)
    pytest.fail("The fit outlived the server")


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


def test_at_most_the_limit_run_at_once() -> None:
    runner = FitRunner(2, 10, 30.0)
    high_water = 0

    async def main() -> list[int]:
        nonlocal high_water

        async def watch() -> None:
            nonlocal high_water
            while True:
                high_water = max(high_water, len(runner._running))
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
