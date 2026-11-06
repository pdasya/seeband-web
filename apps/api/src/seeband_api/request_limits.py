"""Limits that apply before a request reaches its route: its rate by client, and its size.

These run before the body is read or parsed, so that a refused request costs little. The store is
in memory, for each server process. A client's address is not logged, and is dropped by the first
request at least a minute after its client's last.
"""

import ipaddress
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from time import monotonic

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from seeband_api.errors import ErrorResponse, error_response

_SECONDS_PER_MINUTE = 60.0
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

    def __init__(self, app: ASGIApp, limiter: RateLimiter, max_body_bytes: int) -> None:
        self._app = app
        self._limiter = limiter
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if await self._refused_by_rate(scope, receive, send):
            return

        length = _content_length(scope)
        if length is not None and length > self._max_body_bytes:
            await self._refuse_size(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # The client has gone, so there is nobody to answer.
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self._max_body_bytes:
                await self._refuse_size(scope, receive, send)
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

    async def _refused_by_rate(self, scope: Scope, receive: Receive, send: Send) -> bool:
        path = scope["path"]
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

    async def _refuse_size(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            ErrorResponse(
                code="request_too_large",
                message=f"A request can hold at most {self._max_body_bytes} bytes",
                details=[],
            ),
            headers={"Connection": "close"},
        )
        await response(scope, receive, send)
