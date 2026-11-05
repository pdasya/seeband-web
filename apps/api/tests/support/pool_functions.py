"""Functions that a pool's workers run in tests. Workers must be able to import them by name."""

import os
import signal
import time


def sleep_for_a_while() -> None:
    time.sleep(10)


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def double(value: int) -> int:
    return value * 2
