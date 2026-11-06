"""Starts the API as a real server, for tests that need real connections and processes."""

import json
import os
import signal
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2
import pytest

_SERVER_PIDS: dict[int, int] = {}


def server_pid(port: int) -> int:
    return _SERVER_PIDS[port]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def running_server(
    command: list[str],
    port: int,
    log_path: Path,
    env: dict[str, str] | None = None,
    stop_signal: signal.Signals = signal.SIGTERM,
) -> Iterator[httpx2.Client]:
    with log_path.open("wb") as log_file:
        server = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", **(env or {})},
        )
        _SERVER_PIDS[port] = server.pid
        try:
            with httpx2.Client(base_url=f"http://127.0.0.1:{port}") as client:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        client.get("/api/health")
                        break
                    except httpx2.TransportError:
                        if time.monotonic() > deadline or server.poll() is not None:
                            pytest.fail(log_path.read_text(encoding="utf-8"))
                        time.sleep(0.05)
                yield client
        finally:
            server.send_signal(stop_signal)
            server.wait(timeout=20)


def json_lines(text: str) -> list[dict[str, Any]]:
    lines = []
    for line in text.splitlines():
        if line.startswith("{"):
            lines.append(json.loads(line))
    return lines


def worker_pids(server_pid: int) -> list[int]:
    found = subprocess.run(["pgrep", "-P", str(server_pid)], capture_output=True, text=True)
    return [int(pid) for pid in found.stdout.split()]


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


# A request the API accepts. The fake fits of `serve_with_fake_fit.py` ignore it.
FAKE_FIT_BODY = {
    "model": "dpb",
    "fit_mode": "dpb_s",
    "start": {"m_eff": 1.01, "band_gap": 1000.0, "fermi_energy": -100.0},
    "min_temperature_k": 100.0,
    "max_temperature_k": 500.0,
    "measurements": {"seebeck": {"temperature_k": [100.0, 200.0], "values": [2.0e-4, 1.0e-4]}},
}


def wait_for_fit_pids(pid_file: Path, count: int, timeout_s: float = 20.0) -> list[int]:
    """The processes of the fake fits that have started, once there are `count`."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pid_file.exists():
            pids = [int(line) for line in pid_file.read_text(encoding="utf-8").split()]
            if len(pids) >= count:
                return pids
        time.sleep(0.02)
    pytest.fail(f"{count} fit processes did not start")


def wait_until_ended(pids: list[int], timeout_s: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while any(is_running(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.02)
    return not any(is_running(pid) for pid in pids)


def read_events(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """The events of an open stream, as they arrive."""
    for line in lines:
        if line.startswith("data: "):
            yield json.loads(line.removeprefix("data: "))
