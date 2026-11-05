"""What reaches the logs, in the app and through a real server."""

import asyncio
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from seeband_api.__main__ import main as entry_point
from seeband_api.main import create_app
from seeband_api.request_logging import RequestLoggingMiddleware
from seeband_api.settings import Settings
from starlette.types import Message

SECRET = "SECRET-MEASUREMENT-7fd3"
BODY = {"note": SECRET, "seebeck_v_per_k": [1.5e-4, 2.5e-4]}
REQUEST_FIELDS = {"time", "level", "event", "method", "route", "status", "duration_ms"}


def _send_requests_carrying_the_secret(client: Any) -> None:
    """Sends the secret by every route into the server, and checks each request did what it should.

    The status checks matter: without them, a mistake could turn all of these into 404s that never
    reach a handler, and the test would pass without testing anything.
    """
    url = f"/api/test/echo/{SECRET}?query={SECRET}"
    assert client.post(url, json=BODY).json()["note"] == SECRET
    assert client.post(url, json={"note": 1, "seebeck_v_per_k": SECRET}).status_code == 422
    assert client.post(url, json=BODY, headers={"x-note": SECRET}).status_code == 200
    assert (
        client.post(
            url, content=f"{{{SECRET}".encode(), headers={"content-type": "application/json"}
        ).status_code
        == 422
    )
    assert client.post("/api/test/crash", json=BODY).status_code == 500
    assert client.post(f"/api/nothing/{SECRET}?query={SECRET}", json=BODY).status_code == 404
    assert client.get(url).status_code == 405
    assert client.request(SECRET, url).status_code == 405


class _RecordEverything(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def _recorded_logs() -> Iterator[list[logging.LogRecord]]:
    """Records the API's logger. Its `propagate` is off, so the root logger would not see it."""
    logger = logging.getLogger("seeband_api")
    handler = _RecordEverything()
    logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        logger.removeHandler(handler)


def _fields(records: list[logging.LogRecord], event: str) -> list[dict[str, Any]]:
    return [record.__dict__["fields"] for record in records if record.getMessage() == event]


def test_request_line_holds_method_route_status_and_duration() -> None:
    app = create_app()
    with _recorded_logs() as records:
        TestClient(app).get("/api/health")

    [fields] = _fields(records, "request")
    assert set(fields) == {"method", "route", "status", "duration_ms"}
    assert fields["method"] == "GET"
    assert fields["route"] == "/api/health"
    assert fields["status"] == 200
    assert fields["duration_ms"] >= 0


@pytest.mark.parametrize(
    ("path", "route", "status"),
    [
        ("/api/openapi.json", "/api/openapi.json", 200),
        ("/api/docs", "/api/docs", 200),
        (f"/api/nothing/{SECRET}", "<unmatched>", 404),
    ],
)
def test_routes_without_a_template(path: str, route: str, status: int) -> None:
    app = create_app()
    with _recorded_logs() as records:
        TestClient(app).get(path)

    [fields] = _fields(records, "request")
    assert (fields["route"], fields["status"]) == (route, status)


def test_route_is_logged_as_its_template(leaky_app_factory: Callable[[], FastAPI]) -> None:
    app = leaky_app_factory()
    with _recorded_logs() as records:
        TestClient(app).post(f"/api/test/echo/{SECRET}?query=x", json=BODY)

    [fields] = _fields(records, "request")
    assert fields["route"] == "/api/test/echo/{item_id}"


def test_nothing_from_a_request_reaches_the_records(
    leaky_app_factory: Callable[[], FastAPI],
) -> None:
    app = leaky_app_factory()
    with _recorded_logs() as records:
        _send_requests_carrying_the_secret(TestClient(app))

    assert len(_fields(records, "request")) == 8
    for record in records:
        assert SECRET not in record.getMessage()
        assert SECRET not in json.dumps(record.__dict__.get("fields"))
        assert record.exc_info is None


def test_unhandled_exception_logs_type_and_location_only(
    leaky_app_factory: Callable[[], FastAPI],
) -> None:
    app = leaky_app_factory()
    with _recorded_logs() as records:
        TestClient(app).post("/api/test/crash", json=BODY)

    [fields] = _fields(records, "unhandled_exception")
    assert fields["exception_type"] == "RuntimeError"
    assert any(frame.startswith("leaky_app.py:") and "crash" in frame for frame in fields["frames"])
    assert _fields(records, "request")[0]["status"] == 500


def test_exception_after_the_response_started_keeps_its_status(
    leaky_app_factory: Callable[[], FastAPI],
) -> None:
    app = leaky_app_factory()
    with _recorded_logs() as records:
        response = TestClient(app).post("/api/test/crash-while-streaming", json=BODY)

    assert response.status_code == 200
    assert response.content == b"first chunk"
    assert _fields(records, "unhandled_exception")[0]["exception_type"] == "RuntimeError"
    assert _fields(records, "request")[0]["status"] == 200


def test_unknown_method_is_logged_as_other() -> None:
    app = create_app()
    with _recorded_logs() as records:
        TestClient(app).request(SECRET, "/api/health")

    [fields] = _fields(records, "request")
    assert fields["method"] == "OTHER"


def test_duration_is_in_milliseconds(leaky_app_factory: Callable[[], FastAPI]) -> None:
    app = leaky_app_factory()
    with _recorded_logs() as records:
        TestClient(app).get("/api/test/sleep-50-ms")

    [fields] = _fields(records, "request")
    assert 40 <= fields["duration_ms"] < 5000


def _http_scope() -> dict[str, Any]:
    return {"type": "http", "method": "POST", "path": "/api/test", "headers": []}


def _raises(error: BaseException) -> Callable[..., Coroutine[Any, Any, None]]:
    async def app(*_: Any) -> None:
        raise error

    return app


def test_any_exception_becomes_the_500_response() -> None:
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = RequestLoggingMiddleware(_raises(ValueError(SECRET)), frozenset())
    with _recorded_logs() as records:
        asyncio.run(middleware(_http_scope(), None, send))  # type: ignore[arg-type]

    assert sent[0]["status"] == 500
    assert _fields(records, "unhandled_exception")[0]["exception_type"] == "ValueError"
    assert _fields(records, "request")[0]["status"] == 500


def test_cancellation_continues_and_logs_no_status() -> None:
    middleware = RequestLoggingMiddleware(_raises(asyncio.CancelledError()), frozenset())
    with _recorded_logs() as records, pytest.raises(asyncio.CancelledError):
        asyncio.run(middleware(_http_scope(), None, None))  # type: ignore[arg-type]

    assert _fields(records, "unhandled_exception") == []
    assert _fields(records, "request")[0]["status"] is None


def test_failure_to_send_the_500_does_not_carry_the_original_message() -> None:
    async def send(_: Message) -> None:
        raise OSError("connection lost")

    middleware = RequestLoggingMiddleware(_raises(RuntimeError(SECRET)), frozenset())
    with _recorded_logs() as records, pytest.raises(OSError) as raised:
        asyncio.run(middleware(_http_scope(), None, send))  # type: ignore[arg-type]

    assert raised.value.__context__ is None
    assert _fields(records, "request")[0]["status"] is None


def test_log_level_setting_is_applied() -> None:
    app = create_app(Settings(log_level="WARNING"))
    with _recorded_logs() as records:
        TestClient(app).get("/api/health")

    # The handler added by the test sees only what passes the logger's level.
    assert _fields(records, "request") == []
    create_app(Settings(log_level="INFO"))


_SERVER_PIDS: dict[int, int] = {}


def _server_pid(port: int) -> int:
    return _SERVER_PIDS[port]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _running_server(
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
            server.wait(timeout=10)


def _json_lines(text: str) -> list[dict[str, Any]]:
    lines = []
    for line in text.splitlines():
        if line.startswith("{"):
            lines.append(json.loads(line))
    return lines


def _uvicorn_factory_command(support_dir: Path, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "leaky_app:create_app",
        "--app-dir",
        str(support_dir),
        "--port",
        str(port),
    ]


def _uvicorn_run_command(support_dir: Path, port: int) -> list[str]:
    """In this mode the app is created before uvicorn sets up its logging."""
    return [sys.executable, str(support_dir / "serve_with_uvicorn_run.py"), str(port)]


@pytest.mark.parametrize("build_command", [_uvicorn_factory_command, _uvicorn_run_command])
def test_real_server_with_default_uvicorn_settings_logs_nothing_from_requests(
    tmp_path: Path, support_dir: Path, build_command: Callable[[Path, int], list[str]]
) -> None:
    """Uvicorn's own logs are the risk: its access log has query strings, its error log tracebacks.

    This runs uvicorn with its defaults, rather than the project's entry point. So the app must
    protect itself even when someone starts it differently. The API's log level is the widest it
    can be, so that a debug line is checked too.
    """
    port = _free_port()
    log_path = tmp_path / "server.log"
    command = build_command(support_dir, port)

    with _running_server(command, port, log_path, {"SEEBAND_API_LOG_LEVEL": "DEBUG"}) as client:
        _send_requests_carrying_the_secret(client)
        with pytest.raises(httpx2.TransportError):
            client.post("/api/test/crash-while-streaming", json=BODY).read()

    log = log_path.read_text(encoding="utf-8")
    assert SECRET not in log
    assert "first chunk" not in log
    assert "Traceback" not in log
    # Check that these logs really are the server's, and were not empty for some other reason.
    lines = _json_lines(log)
    assert sum(line.get("route") == "/api/test/crash" for line in lines) == 1
    assert sum(line.get("event") == "unhandled_exception" for line in lines) == 2
    assert not re.search(r'"(POST|GET) /', log), "the access log is on"
    assert "Uvicorn running" in log


def test_calculation_through_real_workers_logs_no_values(tmp_path: Path) -> None:
    port = _free_port()
    log_path = tmp_path / "server.log"
    command = [sys.executable, "-m", "seeband_api"]
    env = {"SEEBAND_API_PORT": str(port), "SEEBAND_API_LOG_LEVEL": "DEBUG"}
    measured = "7.123456789e-05"
    body = {
        "model": "spb",
        "fit_mode": "spb_s",
        # A band mass of 0 gives results that are not finite, which makes the core warn.
        "parameters": {"band_mass": 0.0, "fermi_energy": 1234.5678},
        "min_temperature_k": 123.456789,
        "max_temperature_k": 765.4321,
        "measurements": {
            "seebeck": {"temperature_k": [333.3331], "values": [float(measured)]},
        },
    }

    with _running_server(command, port, log_path, env) as client:
        response = client.post("/api/calc", json=body, timeout=30)
        assert response.status_code == 200

    log = log_path.read_text(encoding="utf-8")
    for value in (measured, "1234.5678", "123.456789", "765.4321", "333.3331"):
        assert value not in log
    assert "RuntimeWarning" not in log
    assert sum(line.get("route") == "/api/calc" for line in _json_lines(log)) == 1


def test_parsing_through_real_workers_keeps_nothing(tmp_path: Path) -> None:
    """Neither the log nor any file holds the text, including temporary files."""
    port = _free_port()
    log_path = tmp_path / "server.log"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    secret = "4.321987654e-05"
    rows = "\n".join(f"{100 + row * 0.01:.2f} {secret}" for row in range(40000))
    env = {
        "SEEBAND_API_PORT": str(port),
        "SEEBAND_API_LOG_LEVEL": "DEBUG",
        "TMPDIR": str(temp_dir),
    }
    command = [sys.executable, "-m", "seeband_api"]

    with _running_server(command, port, log_path, env) as client:
        for text in (f"T S\n{rows}\n", f"T S\n100 {secret} x\n"):
            response = client.post(
                "/api/parse",
                json={
                    "text": text,
                    "expected": "seebeck",
                    "interpolate": {"min_temperature_k": 100.0, "max_temperature_k": 400.0},
                },
                timeout=60,
            )
            assert response.status_code == 200
        held = [path for path in temp_dir.rglob("*") if path.is_file()]
        assert not [path for path in held if secret.encode() in path.read_bytes()]

    assert secret not in log_path.read_text(encoding="utf-8")
    assert not [path for path in temp_dir.rglob("*") if path.is_file()]


def _worker_pids(server_pid: int) -> list[int]:
    found = subprocess.run(["pgrep", "-P", str(server_pid)], capture_output=True, text=True)
    return [int(pid) for pid in found.stdout.split()]


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGKILL])
def test_workers_end_with_the_server(tmp_path: Path, stop_signal: signal.Signals) -> None:
    """A signal can end the server before it shuts its pool down."""
    port = _free_port()
    log_path = tmp_path / "server.log"
    body = {
        "model": "spb",
        "fit_mode": "spb_s",
        "parameters": {"band_mass": 1.0, "fermi_energy": 100.0},
        "min_temperature_k": 100,
        "max_temperature_k": 500,
        "points": 5,
    }
    command = [sys.executable, "-m", "seeband_api"]

    with _running_server(
        command, port, log_path, {"SEEBAND_API_PORT": str(port)}, stop_signal=stop_signal
    ) as client:
        assert client.post("/api/calc", json=body, timeout=30).status_code == 200
        server_pid = _server_pid(port)
        workers = _worker_pids(server_pid)
        assert workers

    deadline = time.monotonic() + 15
    while any(_is_running(pid) for pid in workers) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(_is_running(pid) for pid in workers)


def test_entry_point_passes_its_settings_to_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("uvicorn.run", lambda _, **options: calls.append(options))
    monkeypatch.setenv("SEEBAND_API_HOST", "0.0.0.0")
    monkeypatch.setenv("SEEBAND_API_PORT", "9123")

    entry_point()

    assert calls == [
        {"factory": True, "host": "0.0.0.0", "port": 9123, "access_log": False, "ws": "none"}
    ]


def test_entry_point_serves_with_settings_from_the_environment(tmp_path: Path) -> None:
    port = _free_port()
    log_path = tmp_path / "server.log"
    command = [sys.executable, "-m", "seeband_api"]

    with _running_server(command, port, log_path, {"SEEBAND_API_PORT": str(port)}) as client:
        assert client.get("/api/health").json()["status"] == "ok"

    health_lines = [
        line
        for line in _json_lines(log_path.read_text(encoding="utf-8"))
        if line["event"] == "request"
    ]
    assert health_lines
    assert set(health_lines[-1]) == REQUEST_FIELDS
    assert health_lines[-1]["route"] == "/api/health"
