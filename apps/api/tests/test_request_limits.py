"""The limits on rate, size and points, each through the API's error format."""

import asyncio
import json
import logging
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from running_server import free_port, running_server
from seeband_api.main import create_app
from seeband_api.request_limits import RateLimiter, RequestLimitsMiddleware, client_key
from seeband_api.settings import Settings
from seeband_core.model_catalog import registry
from seeband_core.model_scales import default_start
from starlette.responses import Response
from starlette.types import Message, Receive, Scope, Send

_MODE = registry.get("dpb").describe().fit_mode("dpb_s")
_MEASUREMENT = {"temperature_k": [100.0, 200.0, 300.0], "values": [2e-4, 1e-4, 5e-5]}
_FIT = {
    "model": "dpb",
    "fit_mode": "dpb_s",
    "start": default_start(_MODE),
    "min_temperature_k": 100.0,
    "max_temperature_k": 300.0,
    "measurements": {"seebeck": _MEASUREMENT},
}
_CALC = {
    "model": "dpb",
    "fit_mode": "dpb_s",
    "parameters": default_start(_MODE),
    "min_temperature_k": 100.0,
    "max_temperature_k": 300.0,
    "measurements": {"seebeck": _MEASUREMENT},
}
_GUESS = {
    "model": "dpb",
    "temperature_k": _MEASUREMENT["temperature_k"],
    "seebeck_v_per_k": _MEASUREMENT["values"],
}
_PARSE = {"text": "T S\n100 1e-4\n200 2e-4\n300 3e-4\n"}


class _Clock:
    def __init__(self) -> None:
        self.now_s = 1000.0

    def __call__(self) -> float:
        return self.now_s


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


def test_a_client_gets_a_minutes_requests_at_once_then_waits(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 60}, clock)

    assert [limiter.retry_after_s("/a", "x") for _ in range(60)] == [None] * 60
    assert limiter.retry_after_s("/a", "x") == 1


def test_retry_hint_is_when_a_request_will_pass(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 2}, clock)
    limiter.retry_after_s("/a", "x")
    limiter.retry_after_s("/a", "x")

    hint = limiter.retry_after_s("/a", "x")

    assert hint == 30
    clock.now_s += 29
    assert limiter.retry_after_s("/a", "x") == 1
    clock.now_s += 1
    assert limiter.retry_after_s("/a", "x") is None


def test_a_refused_request_takes_nothing(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 60}, clock)
    for _ in range(60):
        limiter.retry_after_s("/a", "x")
    for _ in range(100):
        assert limiter.retry_after_s("/a", "x") == 1

    clock.now_s += 1

    assert limiter.retry_after_s("/a", "x") is None


def test_clients_and_paths_are_counted_apart(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 1, "/b": 1}, clock)

    assert limiter.retry_after_s("/a", "x") is None
    assert limiter.retry_after_s("/a", "x") is not None
    assert limiter.retry_after_s("/a", "y") is None
    assert limiter.retry_after_s("/b", "x") is None


def test_a_bucket_does_not_grow_past_a_minutes_requests(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 4}, clock)
    # Each gap is under a minute, so that the bucket stays in the store.
    clock.now_s += 59
    limiter.retry_after_s("/a", "x")
    clock.now_s += 59

    answers = [limiter.retry_after_s("/a", "x") for _ in range(5)]

    assert answers[:4] == [None] * 4
    assert answers[4] is not None


def test_addresses_are_forgotten_after_a_minute(clock: _Clock) -> None:
    limiter = RateLimiter({"/a": 1}, clock)
    limiter.retry_after_s("/a", "x")
    clock.now_s += 30
    limiter.retry_after_s("/a", "y")
    clock.now_s += 31

    limiter.retry_after_s("/a", "z")

    assert {client for _, client in limiter._buckets} == {"y", "z"}


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (("192.0.2.1", 1), "192.0.2.1"),
        (("2001:db8:1:2:3:4:5:6", 1), "2001:db8:1:2::/64"),
        (("2001:db8:1:2:ffff::", 1), "2001:db8:1:2::/64"),
        (("::ffff:192.0.2.1", 1), "192.0.2.1"),
        (("testclient", 1), "testclient"),
        (None, "unknown"),
    ],
)
def test_client_key(client: Any, expected: str) -> None:
    assert client_key({"client": client}) == expected


def _client(**settings: Any) -> TestClient:
    return TestClient(create_app(Settings(**settings)))


@pytest.mark.parametrize(
    ("path", "setting", "body"),
    [
        ("/api/calc", "calc_per_minute", _CALC),
        ("/api/parse", "parse_per_minute", _PARSE),
        ("/api/guess", "guess_per_minute", _GUESS),
        ("/api/fit", "fit_per_minute", _FIT),
    ],
)
def test_each_route_answers_429_past_its_rate(path: str, setting: str, body: Any) -> None:
    with _client(**{setting: 1}) as client:
        assert client.post(path, json=body).status_code == 200

        refused = client.post(path, json=body)

    assert refused.status_code == 429
    assert refused.json() == {"code": "rate_limited", "message": "Too many requests", "details": []}
    assert 1 <= int(refused.headers["retry-after"]) <= 60


def test_every_route_that_takes_a_body_has_a_rate_limit() -> None:
    """A new route must be added to the limit, or to this test on purpose."""
    paths = create_app(Settings()).openapi()["paths"]

    assert {path for path, operations in paths.items() if "post" in operations} == {
        "/api/calc",
        "/api/parse",
        "/api/guess",
        "/api/fit",
    }


def test_a_root_path_does_not_switch_off_the_rate() -> None:
    sent: list[Message] = []

    async def app(_: Scope, __: Receive, app_send: Send) -> None:
        await Response("ok")({"type": "http"}, __, app_send)

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = RequestLimitsMiddleware(app, RateLimiter({"/api/fit": 1}), 100)
    # As uvicorn gives it with `--root-path /sb`.
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/sb/api/fit",
        "root_path": "/sb",
        "headers": [],
        "client": ("192.0.2.1", 1),
    }

    asyncio.run(middleware(scope, receive, send))
    asyncio.run(middleware(scope, receive, send))

    assert [m["status"] for m in sent if m["type"] == "http.response.start"] == [200, 429]


def test_only_post_counts_towards_a_rate() -> None:
    with _client(guess_per_minute=1) as client:
        assert [client.get("/api/guess").status_code for _ in range(3)] == [405] * 3
        assert client.post("/api/guess", json=_GUESS).status_code == 200


def test_reading_routes_have_no_rate_limit() -> None:
    with _client(calc_per_minute=1, parse_per_minute=1, guess_per_minute=1, fit_per_minute=1) as c:
        assert [c.get("/api/models").status_code for _ in range(5)] == [200] * 5
        assert [c.get("/api/health").status_code for _ in range(5)] == [200] * 5
        assert [c.get("/api/demo").status_code for _ in range(5)] == [200] * 5


def test_a_refused_request_logs_its_route_and_status() -> None:
    records: list[logging.LogRecord] = []

    class Recorder(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    with _client(guess_per_minute=2, max_body_bytes=1000) as client:
        recorder = Recorder()
        logging.getLogger("seeband_api").addHandler(recorder)
        try:
            client.post("/api/guess", json=_GUESS)
            client.post("/api/guess", content=b"x" * 1001)
            client.post("/api/guess", json=_GUESS)
        finally:
            logging.getLogger("seeband_api").removeHandler(recorder)

    fields = [r.__dict__["fields"] for r in records if r.getMessage() == "request"]
    assert [(f["route"], f["status"]) for f in fields] == [
        ("/api/guess", 200),
        ("/api/guess", 413),
        ("/api/guess", 429),
    ]


def _assert_too_large(response: Any, limit: int) -> None:
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
    assert str(limit) in response.json()["message"]
    assert response.headers["connection"] == "close"


def _middleware_call(
    messages: list[Message], headers: list[tuple[bytes, bytes]], max_body_bytes: int = 100
) -> tuple[list[Message], list[Message], int]:
    """Runs the middleware over ASGI messages: what the app received, what it sent, reads made."""
    received: list[Message] = []
    sent: list[Message] = []
    reads = 0

    async def receive() -> Message:
        nonlocal reads
        reads += 1
        return messages.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    async def app(_: Scope, app_receive: Receive, app_send: Send) -> None:
        received.append(await app_receive())
        received.append(await app_receive())
        await Response("ok")({"type": "http"}, app_receive, app_send)

    scope = {"type": "http", "method": "POST", "path": "/x", "headers": headers}
    middleware = RequestLimitsMiddleware(app, RateLimiter({}), max_body_bytes)
    asyncio.run(middleware(scope, receive, send))
    return received, sent, reads


def test_a_declared_size_over_the_limit_is_refused_unread() -> None:
    with _client(max_body_bytes=100) as client:
        response = client.post("/api/parse", content=b"x" * 101)
    _assert_too_large(response, 100)

    received, sent, reads = _middleware_call([], [(b"content-length", b"101")])

    assert received == []
    assert reads == 0
    assert sent[0]["status"] == 413


def test_a_declared_size_at_the_limit_passes() -> None:
    message = {"type": "http.request", "body": b"x" * 100, "more_body": False}
    disconnect = {"type": "http.disconnect"}

    received, sent, _ = _middleware_call([message, disconnect], [(b"content-length", b"100")])

    assert received[0]["body"] == b"x" * 100
    assert sent[0]["status"] == 200


def test_a_body_in_pieces_reaches_the_app_whole_and_a_disconnect_follows() -> None:
    pieces = [
        {"type": "http.request", "body": b"ab", "more_body": True},
        {"type": "http.request", "body": b"cd", "more_body": True},
        {"type": "http.request", "body": b"", "more_body": False},
    ]
    disconnect = {"type": "http.disconnect"}

    received, _, _ = _middleware_call([*pieces, disconnect], [])

    assert received == [{"type": "http.request", "body": b"abcd"}, disconnect]


def test_a_client_that_leaves_during_its_body_reaches_nothing() -> None:
    pieces = [
        {"type": "http.request", "body": b"ab", "more_body": True},
        {"type": "http.disconnect"},
    ]

    received, sent, _ = _middleware_call(pieces, [])

    assert received == []
    assert sent == []


def test_a_body_with_no_declared_size_is_limited_too() -> None:
    def chunks() -> Iterator[bytes]:
        yield b"x" * 60
        yield b"x" * 60

    with _client(max_body_bytes=100) as client:
        response = client.post("/api/parse", content=chunks())

    assert "content-length" not in response.request.headers
    _assert_too_large(response, 100)


def test_a_body_at_the_limit_with_no_declared_size_reaches_the_route_whole() -> None:
    body = json.dumps(_PARSE).encode()

    def chunks() -> Iterator[bytes]:
        yield body

    with _client(max_body_bytes=len(body)) as client:
        response = client.post(
            "/api/parse", content=chunks(), headers={"content-type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json()["row_count"] == 3


def test_the_size_limit_also_covers_a_route_that_does_not_exist() -> None:
    with _client(max_body_bytes=100) as client:
        assert client.post("/api/nothing", content=b"x" * 101).status_code == 413


def _points(count: int) -> dict[str, list[float]]:
    return {
        "temperature_k": [100.0 + row for row in range(count)],
        "values": [1e-4] * count,
    }


@pytest.mark.parametrize(
    ("path", "body", "code"),
    [
        ("/api/calc", _CALC, "invalid_calculation"),
        ("/api/fit", _FIT, "invalid_fit"),
    ],
)
def test_measurements_past_the_limit_are_refused(path: str, body: Any, code: str) -> None:
    with _client(max_points=3) as client:
        accepted = client.post(path, json=body | {"measurements": {"seebeck": _points(3)}})
        refused = client.post(path, json=body | {"measurements": {"seebeck": _points(4)}})

    assert accepted.status_code == 200
    assert refused.status_code == 422
    assert refused.json()["code"] == code
    detail = refused.json()["details"][0]
    assert (detail["location"], detail["code"]) == (
        ["body", "measurements", "seebeck"],
        "too_many_points",
    )
    assert "3" in detail["message"]


def test_points_outside_the_fit_range_count_too() -> None:
    body = _FIT | {"measurements": {"seebeck": _points(4)}, "max_temperature_k": 101.0}
    with _client(max_points=3) as client:
        assert client.post("/api/fit", json=body).status_code == 422


def test_guess_past_the_limit_is_refused() -> None:
    body = {"model": "dpb", "temperature_k": [100.0, 200.0], "seebeck_v_per_k": [1e-4, 2e-4]}
    with _client(max_points=2) as client:
        accepted = client.post("/api/guess", json=body)
        refused = client.post(
            "/api/guess",
            json=body | {"temperature_k": [1.0, 2.0, 3.0], "seebeck_v_per_k": [1e-4] * 3},
        )

    assert accepted.status_code == 200
    assert refused.status_code == 422
    assert refused.json()["code"] == "invalid_guess"
    assert refused.json()["details"][0]["location"] == ["body", "temperature_k"]
    assert refused.json()["details"][0]["code"] == "too_many_points"


def test_parse_past_the_row_limit_is_refused() -> None:
    with _client(max_points=3) as client:
        accepted = client.post("/api/parse", json=_PARSE)
        refused = client.post("/api/parse", json={"text": _PARSE["text"] + "400 4e-4\n"})
        # Lines that are not rows do not count.
        with_notes = client.post("/api/parse", json={"text": "note\nnote\n" + _PARSE["text"]})

    assert accepted.status_code == 200
    assert with_notes.status_code == 200
    assert refused.status_code == 422
    assert refused.json()["code"] == "invalid_parse_request"
    assert refused.json()["details"][0]["code"] == "too_many_rows"


def test_settings_set_the_defaults() -> None:
    fields = Settings.model_fields

    assert fields["max_body_bytes"].default == 10_000_000
    assert fields["max_points"].default == 2000
    assert fields["calc_per_minute"].default == 600
    assert fields["parse_per_minute"].default == 60
    assert fields["guess_per_minute"].default == 60
    assert fields["fit_per_minute"].default == 30
    assert fields["fit_max_per_client"].default == 2


def _guess_with(client: httpx2.Client, forwarded_for: str) -> int:
    response = client.post("/api/guess", json=_GUESS, headers={"x-forwarded-for": forwarded_for})
    return response.status_code


def _rate_server(tmp_path: Path, **env: str) -> Any:
    port = free_port()
    return running_server(
        [sys.executable, "-m", "seeband_api"],
        port,
        tmp_path / "server.log",
        {
            "SEEBAND_API_PORT": str(port),
            "SEEBAND_API_CALC_WORKERS": "1",
            "SEEBAND_API_GUESS_PER_MINUTE": "1",
            **env,
        },
    )


def test_a_trusted_proxy_separates_clients_and_a_client_cannot_choose_its_own(
    tmp_path: Path,
) -> None:
    with _rate_server(tmp_path) as client:
        assert _guess_with(client, "198.51.100.1") == 200
        assert _guess_with(client, "198.51.100.1") == 429
        assert _guess_with(client, "198.51.100.2") == 200
        # What a client sends comes first, and a proxy appends the address it saw.
        assert _guess_with(client, "203.0.113.9, 198.51.100.1") == 429


def test_an_address_that_is_not_trusted_cannot_choose_a_client(tmp_path: Path) -> None:
    env = {"SEEBAND_API_TRUSTED_PROXIES": "192.0.2.1"}
    with _rate_server(tmp_path, **env) as client:
        assert _guess_with(client, "198.51.100.1") == 200
        assert _guess_with(client, "198.51.100.2") == 429


def test_a_large_declared_body_is_answered_before_it_is_sent(tmp_path: Path) -> None:
    """Sending the body too would race with the server closing, as the README says."""
    port = free_port()
    command = [sys.executable, "-m", "seeband_api"]
    env = {"SEEBAND_API_PORT": str(port), "SEEBAND_API_CALC_WORKERS": "1"}
    with running_server(command, port, tmp_path / "server.log", env) as client:
        with socket.create_connection(("127.0.0.1", port)) as connection:
            connection.sendall(
                b"POST /api/parse HTTP/1.1\r\nHost: test\r\nContent-Type: application/json\r\n"
                b"Content-Length: 40000000\r\n\r\n"
            )
            connection.settimeout(10)
            answer = b""
            while chunk := connection.recv(4096):
                answer += chunk
        assert client.get("/api/health").status_code == 200

    assert answer.startswith(b"HTTP/1.1 413")
    assert b"request_too_large" in answer
