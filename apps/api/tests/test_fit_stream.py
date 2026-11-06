"""`POST /api/fit` through a real server and real connections.

A test client buffers a response and cannot close a connection part of the way through.
"""

import json
import socket
import struct
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import fit_functions
import httpx2
from running_server import (
    FAKE_FIT_BODY,
    free_port,
    is_running,
    json_lines,
    read_events,
    running_server,
    wait_for_fit_pids,
    wait_until_ended,
)


class _Server:
    def __init__(self, client: httpx2.Client, pid_file: Path, log_path: Path, port: int) -> None:
        self.client = client
        self.pid_file = pid_file
        self.log_path = log_path
        self.port = port

    def stream(self) -> Any:
        return self.client.stream("POST", "/api/fit", json=FAKE_FIT_BODY, timeout=60)

    def log(self) -> str:
        return self.log_path.read_text(encoding="utf-8")


@contextmanager
def _server(tmp_path: Path, support_dir: Path, fake_fit: str, **settings: Any) -> Iterator[_Server]:
    port = free_port()
    log_path = tmp_path / "server.log"
    pid_file = tmp_path / "fit_pids"
    env = {
        "SEEBAND_API_PORT": str(port),
        "SEEBAND_API_CALC_WORKERS": "1",
        "FAKE_FIT": fake_fit,
        "FAKE_FIT_PID_FILE": str(pid_file),
        **{f"SEEBAND_API_{name.upper()}": str(value) for name, value in settings.items()},
    }
    command = [sys.executable, str(support_dir / "serve_with_fake_fit.py")]
    with running_server(command, port, log_path, env) as client:
        yield _Server(client, pid_file, log_path, port)


def test_events_arrive_while_the_fit_runs(tmp_path: Path, support_dir: Path) -> None:
    with (
        _server(tmp_path, support_dir, "iterate_then_hang") as server,
        server.stream() as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        events = read_events(response.iter_lines())

        # The fit hangs after these, so they cannot have waited for its end.
        assert next(events) == {"type": "started"}
        for expected in fit_functions.FAKE_ITERATIONS:
            assert next(events) == {
                "type": "iteration",
                "iteration": expected.iteration,
                "parameters": dict(expected.parameters),
            }


def test_closing_the_connection_ends_the_fit_and_leaves_the_last_values(
    tmp_path: Path, support_dir: Path
) -> None:
    with _server(
        tmp_path, support_dir, "iterate_then_hang", fit_max_running=1, fit_max_waiting=0
    ) as server:
        last: dict[str, Any] = {}
        with server.stream() as response:
            for event in read_events(response.iter_lines()):
                if event["type"] == "iteration":
                    last = event
                    if event["iteration"] == 2:
                        break
        pids = wait_for_fit_pids(server.pid_file, 1)

        assert wait_until_ended(pids, 5.0)
        assert last["parameters"] == dict(fit_functions.FAKE_ITERATIONS[1].parameters)
        # The only place is free again, as otherwise this gets a 429.
        with server.stream() as second:
            assert second.status_code == 200
            second_events = read_events(second.iter_lines())
            assert next(second_events) == {"type": "started"}

    lines = [line for line in json_lines(server.log()) if line.get("route") == "/api/fit"]
    assert len(lines) >= 1
    assert lines[0]["status"] == 200
    assert "Traceback" not in server.log()


def test_closing_the_connection_ends_a_fit_that_sends_nothing(
    tmp_path: Path, support_dir: Path
) -> None:
    with _server(tmp_path, support_dir, "hang") as server:
        with server.stream() as response:
            events = read_events(response.iter_lines())
            assert next(events) == {"type": "started"}
            pids = wait_for_fit_pids(server.pid_file, 1)
            assert all(is_running(pid) for pid in pids)

        assert wait_until_ended(pids, 5.0)


def test_a_connection_reset_ends_the_fit(tmp_path: Path, support_dir: Path) -> None:
    with _server(tmp_path, support_dir, "hang") as server:
        body = json.dumps(FAKE_FIT_BODY).encode()
        request = (
            b"POST /api/fit HTTP/1.1\r\nHost: test\r\nContent-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        connection = socket.create_connection(("127.0.0.1", server.port))
        connection.sendall(request)
        pids = wait_for_fit_pids(server.pid_file, 1)

        # A linger time of 0 makes a close send a reset, as a crash of the client's network could.
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        connection.close()

        assert wait_until_ended(pids, 5.0)
        assert "Traceback" not in server.log()


def test_a_client_that_leaves_the_queue_starts_nothing_and_gives_back_its_place(
    tmp_path: Path, support_dir: Path
) -> None:
    with (
        _server(tmp_path, support_dir, "hang", fit_max_running=1, fit_max_waiting=1) as server,
        server.stream() as running,
    ):
        events = read_events(running.iter_lines())
        assert next(events) == {"type": "started"}
        wait_for_fit_pids(server.pid_file, 1)

        with server.stream() as waiting:
            # A waiting client has its answer, with no event until the fit starts.
            assert waiting.status_code == 200
            refused = server.client.post("/api/fit", json=FAKE_FIT_BODY)
            assert refused.status_code == 429
            assert refused.json()["code"] == "fit_queue_full"
            assert refused.headers["retry-after"] == "5"

        with server.stream() as replacement:
            assert replacement.status_code == 200
        assert len(wait_for_fit_pids(server.pid_file, 1)) == 1


def test_a_waiting_fit_starts_when_a_place_comes_free(tmp_path: Path, support_dir: Path) -> None:
    with _server(tmp_path, support_dir, "hang", fit_max_running=1, fit_max_waiting=1) as server:
        with server.stream() as running:
            running_events = read_events(running.iter_lines())
            assert next(running_events) == {"type": "started"}
            wait_for_fit_pids(server.pid_file, 1)
            waiting = server.client.send(
                server.client.build_request("POST", "/api/fit", json=FAKE_FIT_BODY, timeout=60),
                stream=True,
            )
        try:
            waiting_events = read_events(waiting.iter_lines())
            assert next(waiting_events) == {"type": "started"}
            assert len(wait_for_fit_pids(server.pid_file, 2)) == 2
        finally:
            waiting.close()


def test_time_limit_ends_the_stream_with_an_error_and_ends_the_fit(
    tmp_path: Path, support_dir: Path
) -> None:
    with _server(tmp_path, support_dir, "iterate_then_hang", fit_timeout_s=3) as server:
        with server.stream() as response:
            events = list(read_events(response.iter_lines()))

        assert [event["type"] for event in events] == [
            "started",
            "iteration",
            "iteration",
            "error",
        ]
        assert events[-1]["error"]["code"] == "fit_timeout"
        assert wait_until_ended(wait_for_fit_pids(server.pid_file, 1), 5.0)


def test_process_that_dies_ends_the_stream_with_an_error(tmp_path: Path, support_dir: Path) -> None:
    with (
        _server(tmp_path, support_dir, "iterate_then_die") as server,
        server.stream() as response,
    ):
        events = list(read_events(response.iter_lines()))

    assert [event["type"] for event in events] == ["started", "iteration", "error"]
    assert events[-1]["error"]["code"] == "fit_process_died"


def test_exception_in_the_process_keeps_its_text_out_of_the_stream_and_log(
    tmp_path: Path, support_dir: Path
) -> None:
    with _server(tmp_path, support_dir, "raise") as server:
        with server.stream() as response:
            text = "\n".join(response.iter_lines())

    assert "SECRET-VALUE" not in text
    assert "SECRET-VALUE" not in server.log()
    assert "Traceback" not in server.log()
    assert list(read_events(iter(text.splitlines())))[-1]["error"]["code"] == "fit_failed"


def test_values_that_are_not_finite_are_null(tmp_path: Path, support_dir: Path) -> None:
    with _server(tmp_path, support_dir, "not_finite") as server:
        with server.stream() as response:
            events = list(read_events(response.iter_lines()))

    assert events[1]["parameters"] == {"m_eff": None, "band_gap": 900.0}
    assert events[2]["result"]["parameters"] == {"m_eff": None, "band_gap": 900.0}


def test_refused_requests_are_plain_errors_through_a_real_server(
    tmp_path: Path, support_dir: Path
) -> None:
    with _server(tmp_path, support_dir, "hang") as server:
        response = server.client.post("/api/fit", json=FAKE_FIT_BODY | {"model": "nope"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.json()["code"] == "invalid_fit"
    assert not server.pid_file.exists()
