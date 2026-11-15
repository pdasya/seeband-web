"""Limits that apply before a request reaches its route: its rate by client, and its size.

These run before the body is read or parsed, so that a refused request costs little. The store is
in memory, for each server process. A client's address is not logged. With requests coming in, it is
dropped within about 2 minutes of its client's last request, and with none, stays until the next.
"""

import asyncio
import ipaddress
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from time import monotonic

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from seeband_api.errors import ErrorResponse, error_response

_SECONDS_PER_MINUTE = 60.0
# A probe of health must get through however busy the server is.
_NEVER_REFUSED = frozenset({"/api/health"})
# A request refused for being one too many can come back as soon as one ends.
_BUSY_RETRY_AFTER_S = 1
_IPV6_NETWORK_BITS = 64


def client_key(scope: Scope) -> str:
    """What the limits count a client by.

    One user usually holds a whole IPv6 /64, so counting single addresses would limit nothing. The
    server sets the address, and takes it from `X-Forwarded-For` only from a trusted proxy.
    """
    client = scope.get("client")
    if client is None:
        return "unknown"
    host: str = client[0]
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(address, ipaddress.IPv4Address):
        return str(address)
    if address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network((address, _IPV6_NETWORK_BITS), strict=False))


@dataclass
class _Bucket:
    tokens: float
    updated_s: float


class RateLimiter:
    """A token bucket for each client and path, which holds up to one minute's requests.

    So a client can use a whole minute's requests at once, and a bucket left for a minute is full
    again, which is the same as having none.
    """

    def __init__(
        self, per_minute: Mapping[str, int], clock: Callable[[], float] = monotonic
    ) -> None:
        self._per_minute = per_minute
        self._clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._pruned_s = clock()

    def limits(self, path: str) -> bool:
        return path in self._per_minute

    def retry_after_s(self, path: str, client: str) -> int | None:
        """Takes a token, or returns the whole seconds until there is one."""
        limit = self._per_minute[path]
        now = self._clock()
        self._prune(now)
        bucket = self._buckets.setdefault((path, client), _Bucket(float(limit), now))
        per_second = limit / _SECONDS_PER_MINUTE
        bucket.tokens = min(limit, bucket.tokens + (now - bucket.updated_s) * per_second)
        bucket.updated_s = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return None
        return math.ceil((1 - bucket.tokens) / per_second)

    def _prune(self, now: float) -> None:
        if now - self._pruned_s < _SECONDS_PER_MINUTE:
            return
        self._pruned_s = now
        self._buckets = {
            key: bucket
            for key, bucket in self._buckets.items()
            if now - bucket.updated_s < _SECONDS_PER_MINUTE
        }


def _route_path(scope: Scope) -> str:
    """The path that routes see. `path` starts with a server's root path, and routing drops it.

    A trailing slash is dropped too, as a route redirects `/api/calc/` to `/api/calc`, so its
    limits apply to both.
    """
    path: str = scope["path"]
    path = path.removeprefix(scope.get("root_path", ""))
    return path.rstrip("/") or "/"


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            return int(value) if value.isdigit() else None
    return None


class RequestLimitsMiddleware:
    """Refuses a request over its rate or size, and otherwise passes on the whole body.

    It reads the body itself, so that a body with no `Content-Length` is limited too, and an error
    from reading it never passes through the route. A pure ASGI middleware, as it must not interfere
    with streaming responses.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: RateLimiter,
        max_body_bytes: int,
        max_body_bytes_by_path: Mapping[str, int] | None = None,
        body_timeout_s: float | None = None,
        body_idle_timeout_s: float | None = None,
        max_concurrent_requests: int | None = None,
        per_client_paths: frozenset[str] = frozenset(),
        max_per_client: int | None = None,
    ) -> None:
        self._app = app
        self._limiter = limiter
        self._max_body_bytes = max_body_bytes
        # Routes that take numbers rather than a file have a smaller limit of their own.
        self._max_body_bytes_by_path = max_body_bytes_by_path or {}
        # How long the whole body may take to arrive, and how long it may pause. A route's answer,
        # such as a fit's stream, is not limited, as it begins only once the body is here.
        self._body_timeout_s = body_timeout_s
        self._body_idle_timeout_s = body_idle_timeout_s
        # Requests at once, past which a fast 503. The health route is never refused, so that a
        # probe does not restart a server that is only busy.
        self._max_concurrent_requests = max_concurrent_requests
        self._in_flight = 0
        # Routes whose requests share the calculation pool, and how many one client may have at
        # once. Counted before the body is read, so that a client over it costs nothing to refuse.
        self._per_client_paths = per_client_paths
        self._max_per_client = max_per_client
        self._client_in_flight: dict[str, int] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if await self._refused_by_rate(scope, receive, send):
            return

        path = _route_path(scope)
        counted = path not in _NEVER_REFUSED
        if (
            counted
            and self._max_concurrent_requests is not None
            and self._in_flight >= self._max_concurrent_requests
        ):
            await self._refuse(
                scope,
                receive,
                send,
                HTTPStatus.SERVICE_UNAVAILABLE,
                "server_busy",
                "Too many requests at once. Try again shortly.",
            )
            return
        client = client_key(scope) if path in self._per_client_paths else None
        if (
            client is not None
            and self._max_per_client is not None
            and self._client_in_flight.get(client, 0) >= self._max_per_client
        ):
            await self._refuse(
                scope,
                receive,
                send,
                HTTPStatus.TOO_MANY_REQUESTS,
                "client_calc_limit",
                f"At most {self._max_per_client} calculations of one client at once",
            )
            return

        if counted:
            self._in_flight += 1
        if client is not None:
            self._client_in_flight[client] = self._client_in_flight.get(client, 0) + 1
        try:
            await self._read_then_call(scope, receive, send, path)
        finally:
            if counted:
                self._in_flight -= 1
            if client is not None:
                left = self._client_in_flight[client] - 1
                if left:
                    self._client_in_flight[client] = left
                else:
                    del self._client_in_flight[client]

    async def _read_then_call(self, scope: Scope, receive: Receive, send: Send, path: str) -> None:
        limit = self._max_body_bytes_by_path.get(path, self._max_body_bytes)
        length = _content_length(scope)
        if length is not None and length > limit:
            await self._refuse_size(scope, receive, send, limit)
            return
        chunks: list[bytes] = []
        size = 0
        loop = asyncio.get_running_loop()
        deadline = None if self._body_timeout_s is None else loop.time() + self._body_timeout_s
        while True:
            waits = [
                wait
                for wait in (
                    None if deadline is None else max(deadline - loop.time(), 0),
                    self._body_idle_timeout_s,
                )
                if wait is not None
            ]
            try:
                message = await asyncio.wait_for(receive(), min(waits) if waits else None)
            except TimeoutError:
                await self._refuse_slow_body(scope, receive, send)
                return
            if message["type"] != "http.request":
                return  # The client has gone, so there is nobody to answer.
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                await self._refuse_size(scope, receive, send, limit)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        pending: Message | None = {"type": "http.request", "body": b"".join(chunks)}
        chunks.clear()

        async def receive_body_then_continue() -> Message:
            nonlocal pending
            if pending is None:
                return await receive()
            message, pending = pending, None
            return message

        await self._app(scope, receive_body_then_continue, send)

    async def _refuse(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        status: HTTPStatus,
        code: str,
        message: str,
    ) -> None:
        response = error_response(
            status,
            ErrorResponse(code=code, message=message, details=[]),
            # The body stays unread, so the server cannot reuse this connection anyway.
            headers={"Retry-After": str(_BUSY_RETRY_AFTER_S), "Connection": "close"},
        )
        await response(scope, receive, send)

    async def _refused_by_rate(self, scope: Scope, receive: Receive, send: Send) -> bool:
        path = _route_path(scope)
        if scope["method"] != "POST" or not self._limiter.limits(path):
            return False
        retry_after_s = self._limiter.retry_after_s(path, client_key(scope))
        if retry_after_s is None:
            return False
        response = error_response(
            HTTPStatus.TOO_MANY_REQUESTS,
            ErrorResponse(code="rate_limited", message="Too many requests", details=[]),
            # The body stays unread, so the server cannot reuse this connection anyway.
            headers={"Retry-After": str(retry_after_s), "Connection": "close"},
        )
        await response(scope, receive, send)
        return True

    async def _refuse_slow_body(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            HTTPStatus.REQUEST_TIMEOUT,
            ErrorResponse(
                code="request_timeout",
                message=(
                    f"A request's body must arrive within {self._body_timeout_s} s, "
                    f"with no pause over {self._body_idle_timeout_s} s"
                ),
                details=[],
            ),
            headers={"Connection": "close"},
        )
        await response(scope, receive, send)

    async def _refuse_size(self, scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        response = error_response(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            ErrorResponse(
                code="request_too_large",
                message=f"A request can hold at most {limit} bytes",
                details=[],
            ),
            headers={"Connection": "close"},
        )
        await response(scope, receive, send)
