"""Functions that a pool's workers run in tests. Workers must be able to import them by name."""

import os
import signal
import time

from seeband_api.calc_worker import CalculationFailed


def sleep_for_a_while() -> None:
    time.sleep(10)


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
