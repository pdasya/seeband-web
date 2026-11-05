"""What reaches the logs, in the app and through a real server."""

import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_api.settings import Settings

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
    assert client.get(f"/api/test/echo/{SECRET}?query={SECRET}").status_code == 405


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

    assert len(_fields(records, "request")) == 7
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


def test_log_level_setting_is_applied() -> None:
    app = create_app(Settings(log_level="WARNING"))
    with _recorded_logs() as records:
        TestClient(app).get("/api/health")

    # The handler added by the test sees only what passes the logger's level.
    assert _fields(records, "request") == []
    create_app(Settings(log_level="INFO"))


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _running_server(
    command: list[str], port: int, log_path: Path, env: dict[str, str] | None = None
) -> Iterator[httpx2.Client]:
    with log_path.open("wb") as log_file:
        server = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", **(env or {})},
        )
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
            server.terminate()
            server.wait(timeout=10)


def _json_lines(text: str) -> list[dict[str, Any]]:
    lines = []
    for line in text.splitlines():
        if line.startswith("{"):
            lines.append(json.loads(line))
    return lines


def test_real_server_with_default_uvicorn_settings_logs_nothing_from_requests(
    tmp_path: Path, support_dir: Path
) -> None:
    """Uvicorn's own logs are the risk: its access log has query strings, its error log tracebacks.

    This runs plain `uvicorn`, with its defaults, rather than the project's entry point. So the
    app must protect itself even when someone starts it differently.
    """
    port = _free_port()
    log_path = tmp_path / "server.log"
    command = [
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

    with _running_server(command, port, log_path) as client:
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
