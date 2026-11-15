"""A13: a large or invalid request costs little, and answers with little.

Before, a 9.6 MB body with an error in each value took 18 s, answered 349 MB and peaked the
server at 5.8 GB, holding up `/api/health` for 5.6 s.
"""

import json
import subprocess
import sys
import threading
import time
import tracemalloc
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from running_server import free_port, running_server, server_pid
from seeband_api.errors import MAX_ERROR_DETAILS
from seeband_api.main import create_app
from seeband_api.request_checks import MAX_LISTED_POINTS, MAX_PARAMETERS
from seeband_api.settings import Settings

ANSWER_LIMIT_BYTES = 64_000
TIME_LIMIT_S = 0.5


def _invalid_body(path: str, size: int) -> bytes:
    """A body of about `size` bytes with a wrong value in each place a number goes."""
    bad = ["x"] * (size // 10)
    if path == "/api/guess":
        body: dict[str, Any] = {"model": "dpb", "temperature_k": bad, "seebeck_v_per_k": bad}
    else:
        measurements = {"seebeck": {"temperature_k": bad, "values": bad}}
        names = "start" if path == "/api/fit" else "parameters"
        body = {"model": "dpb", "fit_mode": "dpb_s", names: {}, "measurements": measurements}
        body |= {"min_temperature_k": 50, "max_temperature_k": 800}
    return json.dumps(body).encode()


@pytest.fixture(scope="module")
def client() -> Any:
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def _timed(client: TestClient, path: str, content: bytes) -> tuple[Any, float, int]:
    tracemalloc.start()
    started = time.perf_counter()
    response = client.post(path, content=content, headers={"Content-Type": "application/json"})
    elapsed = time.perf_counter() - started
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return response, elapsed, peak


@pytest.mark.parametrize("path", ["/api/calc", "/api/fit", "/api/guess"])
def test_a_96_mb_body_with_a_wrong_value_everywhere_is_refused_at_once(
    client: TestClient, path: str
) -> None:
    content = _invalid_body(path, 9_600_000)
    assert len(content) > 9_000_000

    response, elapsed, _ = _timed(client, path, content)

    # Over its route's limit, so it is refused before it is read, not validated.
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
    assert elapsed < TIME_LIMIT_S
    assert len(response.content) < ANSWER_LIMIT_BYTES


@pytest.mark.parametrize("path", ["/api/calc", "/api/fit", "/api/guess"])
def test_a_body_just_under_the_limit_with_a_wrong_value_everywhere_is_cheap(
    client: TestClient, path: str
) -> None:
    content = _invalid_body(path, 990_000)
    assert len(content) <= Settings().max_json_body_bytes

    response, elapsed, peak = _timed(client, path, content)

    assert response.status_code == 422
    assert elapsed < TIME_LIMIT_S
    assert len(response.content) < ANSWER_LIMIT_BYTES
    assert peak < 50_000_000
    # A list stops at its first wrong value.
    assert len(response.json()["details"]) <= 2


def test_a_dict_with_too_many_entries_is_refused_before_its_values(client: TestClient) -> None:
    parameters = {f"p{index}": "x" for index in range(60_000)}
    content = json.dumps(
        {
            "model": "dpb",
            "fit_mode": "dpb_s",
            "parameters": parameters,
            "min_temperature_k": 50,
            "max_temperature_k": 800,
        }
    ).encode()

    response, elapsed, _ = _timed(client, "/api/calc", content)

    assert response.status_code == 422
    assert [(d["location"], d["code"]) for d in response.json()["details"]] == [
        (["body", "parameters"], "too_long")
    ]
    assert elapsed < TIME_LIMIT_S


def test_a_list_longer_than_any_setting_allows_is_refused_whole(client: TestClient) -> None:
    values = [1e-4] * (MAX_LISTED_POINTS + 1)
    response = client.post(
        "/api/guess",
        json={"model": "dpb", "temperature_k": [300.0] * len(values), "seebeck_v_per_k": values},
    )

    assert response.status_code in (413, 422)
    if response.status_code == 422:
        assert {d["code"] for d in response.json()["details"]} == {"too_long"}


def test_validation_details_stop_at_50_and_count_the_rest(client: TestClient) -> None:
    parameters = {f"p{index}": "x" for index in range(MAX_PARAMETERS)}
    response = client.post(
        "/api/calc",
        json={
            "model": "dpb",
            "fit_mode": "dpb_s",
            "parameters": parameters,
            "min_temperature_k": 50,
            "max_temperature_k": 800,
        },
    )

    body = response.json()
    assert response.status_code == 422
    assert len(body["details"]) == MAX_ERROR_DETAILS
    assert body["details_omitted"] == MAX_PARAMETERS - MAX_ERROR_DETAILS


def test_route_details_stop_at_50_too(client: TestClient) -> None:
    # Each unknown name is a detail of its own, as are the missing ones.
    parameters = {f"p{index}": 1.0 for index in range(MAX_PARAMETERS)}
    response = client.post(
        "/api/calc",
        json={
            "model": "dpb",
            "fit_mode": "dpb_s",
            "parameters": parameters,
            "min_temperature_k": 50,
            "max_temperature_k": 800,
        },
    )

    body = response.json()
    assert response.status_code == 422
    assert len(body["details"]) == MAX_ERROR_DETAILS
    assert body["details_omitted"] > 0


def test_a_few_details_are_all_given_with_no_count(client: TestClient) -> None:
    response = client.post("/api/calc", json={"model": "dpb"})
    assert response.status_code == 422
    assert "details_omitted" not in response.json()


@pytest.mark.parametrize("path", ["/api/calc", "/api/fit", "/api/guess", "/api/band-diagram"])
def test_routes_of_numbers_take_a_megabyte_and_parse_takes_a_file(
    client: TestClient, path: str
) -> None:
    limit = Settings().max_json_body_bytes
    over = client.post(path, content=b" " * (limit + 1))
    assert over.status_code == 413
    assert str(limit) in over.json()["message"]

    # A file's text of 2 MB is still read by parse.
    text = "T S\n" + "300 1e-4\n" * 4
    parsed = client.post("/api/parse", json={"text": text + " " * 2_000_000})
    assert parsed.status_code in (200, 422)
    assert parsed.json().get("code") != "request_too_large"


def test_a_text_with_too_many_rows_is_refused_before_it_is_read(client: TestClient) -> None:
    text = "T S\n" + "300 1\n" * 300_000

    started = time.perf_counter()
    response = client.post("/api/parse", json={"text": text})
    elapsed = time.perf_counter() - started

    assert response.status_code == 422
    assert [d["code"] for d in response.json()["details"]] == ["too_many_rows"]
    # Reading 300000 rows takes about a second; counting their starts far less.
    assert elapsed < TIME_LIMIT_S


def _rss_bytes(pid: int) -> int:
    found = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    return int(found.stdout.strip()) * 1024


def test_a_real_server_stays_small_and_answers_health_during_invalid_bodies(
    tmp_path: Path,
) -> None:
    port = free_port()
    command = [sys.executable, "-m", "seeband_api"]
    env = {
        "SEEBAND_API_PORT": str(port),
        "SEEBAND_API_CALC_WORKERS": "1",
        "SEEBAND_API_CALC_PER_MINUTE": "100000",
        "SEEBAND_API_FIT_PER_MINUTE": "100000",
        "SEEBAND_API_GUESS_PER_MINUTE": "100000",
    }
    with running_server(command, port, tmp_path / "server.log", env) as client:
        client.get("/api/health")
        before = _rss_bytes(server_pid(port))
        bodies = [
            (path, _invalid_body(path, size))
            for path in ("/api/calc", "/api/fit", "/api/guess")
            for size in (990_000, 9_600_000)
        ]
        answers: list[tuple[int, int]] = []
        stop = threading.Event()

        def send_invalid_bodies() -> None:
            import httpx2

            with httpx2.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as sender:
                while not stop.is_set():
                    for path, content in bodies:
                        response = sender.post(
                            path, content=content, headers={"Content-Type": "application/json"}
                        )
                        answers.append((response.status_code, len(response.content)))

        sender = threading.Thread(target=send_invalid_bodies)
        sender.start()
        probes: list[float] = []
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                started = time.perf_counter()
                assert client.get("/api/health").status_code == 200
                probes.append(time.perf_counter() - started)
                time.sleep(0.02)
        finally:
            stop.set()
            sender.join(timeout=60)
        after = _rss_bytes(server_pid(port))

    assert answers, "no invalid body was answered"
    assert {status for status, _ in answers} <= {413, 422}
    assert max(size for _, size in answers) < ANSWER_LIMIT_BYTES
    assert max(probes) < 0.1
    assert after - before < 50_000_000
