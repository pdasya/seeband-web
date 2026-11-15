"""Functions that a pool's workers run in tests. Workers must be able to import them by name."""

import os
import signal
import sys
import time

from seeband_api.calc_worker import CalculationFailed


def sleep_for_a_while() -> None:
    time.sleep(10)


def sleep_seconds(seconds: float) -> float:
    time.sleep(seconds)
    return seconds


def sleep_then_die(seconds: float) -> None:
    time.sleep(seconds)
    die()


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def double(value: int) -> int:
    return value * 2


def sleep_through_a_guess(*_: object) -> None:
    time.sleep(10)


def die_during_a_guess(*_: object) -> None:
    die()


def fail_a_guess(*_: object) -> None:
    raise CalculationFailed("ValueError")


def slow_warm_up() -> None:
    time.sleep(0.6)


def loaded_modules(names: list[str]) -> list[str]:
    """The modules among `names` that the worker holds."""
    return [name for name in names if name in sys.modules]


def hang_the_first_time(flag: str) -> None:
    """Hangs if `flag` does not exist yet, after creating it, so only the first worker hangs."""
    try:
        with open(flag, "x", encoding="utf-8"):
            pass
    except FileExistsError:
        return
    time.sleep(30)


def parent_pid() -> int:
    return os.getppid()
