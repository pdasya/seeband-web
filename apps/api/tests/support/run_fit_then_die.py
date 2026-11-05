"""Starts a fit that hangs, then kills this process, as a crash of the server would."""

import asyncio
import os
import signal
import sys

import fit_functions
from seeband_api.fit_runner import FitRunner


async def main(pid_file: str) -> None:
    runner = FitRunner(1, 0, 60.0)
    task = asyncio.create_task(runner.run(fit_functions.write_pid_and_hang, pid_file))
    while not (os.path.exists(pid_file) and open(pid_file, encoding="utf-8").read()):
        await asyncio.sleep(0.02)
    os.kill(os.getpid(), signal.SIGKILL)
    await task


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
