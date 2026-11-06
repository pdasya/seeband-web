"""Functions that a fit's process runs in tests. Spawned processes import them by name."""

import os
import signal
import time
from collections.abc import Callable


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
