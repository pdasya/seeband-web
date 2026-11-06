"""Functions that a fit's process runs in tests. Spawned processes import them by name."""

import math
import os
import signal
import time
from collections.abc import Callable
from typing import Any

from seeband_core.model_interface import FitResult, IterationUpdate


def double(value: int, send: Callable[[int], None]) -> int:
    return value * 2


def iterate_then_answer(send: Callable[[int], None]) -> str:
    for iteration in range(1, 4):
        send(iteration)
    return "done"


def sleep_then_answer(seconds: float, send: Callable[[int], None]) -> str:
    time.sleep(seconds)
    return "woke"


def hang(send: Callable[[int], None]) -> None:
    send(1)
    time.sleep(120)


def hang_ignoring_terminate(send: Callable[[int], None]) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    send(1)
    time.sleep(120)


def die(send: Callable[[int], None]) -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def exit_quietly(send: Callable[[int], None]) -> None:
    os._exit(0)


def raise_with_a_value(value: str, send: Callable[[int], None]) -> None:
    raise RuntimeError(value)


def write_pid_and_hang(path: str, send: Callable[[int], None]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(str(os.getpid()))
    time.sleep(120)


def hang_with_a_large_request(blob: bytes, send: Callable[[int], None]) -> None:
    time.sleep(120)


def exit_with_a_value(value: str, send: Callable[[int], None]) -> None:
    raise SystemExit(value)


FAKE_ITERATIONS = [
    IterationUpdate(1, {"m_eff": 1.5, "band_gap": 900.0, "fermi_energy": -50.0}),
    IterationUpdate(2, {"m_eff": 1.25, "band_gap": 850.0, "fermi_energy": -40.0}),
]


def _record_pid() -> None:
    with open(os.environ["FAKE_FIT_PID_FILE"], "a", encoding="utf-8") as file:
        file.write(f"{os.getpid()}\n")


def fake_iterate_then_hang(_: str, __: Any, send: Callable[[IterationUpdate], None]) -> None:
    _record_pid()
    for update in FAKE_ITERATIONS:
        send(update)
    time.sleep(120)


def fake_hang(_: str, __: Any, send: Callable[[IterationUpdate], None]) -> None:
    _record_pid()
    time.sleep(120)


def fake_iterate_then_die(_: str, __: Any, send: Callable[[IterationUpdate], None]) -> None:
    _record_pid()
    send(FAKE_ITERATIONS[0])
    os.kill(os.getpid(), signal.SIGKILL)


def fake_raise(_: str, __: Any, send: Callable[[IterationUpdate], None]) -> None:
    raise RuntimeError("SECRET-VALUE")


def fake_not_finite(_: str, __: Any, send: Callable[[IterationUpdate], None]) -> FitResult:
    send(IterationUpdate(1, {"m_eff": math.nan, "band_gap": 900.0}))
    return FitResult({"m_eff": math.inf, "band_gap": 900.0}, "converged", iterations=1)
