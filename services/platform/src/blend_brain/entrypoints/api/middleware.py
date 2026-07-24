"""Pure ASGI middleware for request context and security headers."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from starlette.datastructures import Headers, MutableHeaders

from blend_brain.shared.application.request_context import reset_request_id, set_request_id

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger(__name__)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _resolve_request_id(headers: Headers, header_name: str) -> str:
    candidate = headers.get(header_name)
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


class RequestContextMiddleware:
    """Bind a safe correlation ID and emit one structured access event."""

    def __init__(self, app: ASGIApp, request_id_header: str) -> None:
        self.app = app
        self.request_id_header = request_id_header

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(Headers(scope=scope), self.request_id_header)
        token = set_request_id(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                if self.request_id_header not in headers:
                    headers.append(self.request_id_header, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            logger.info(
                "request.completed",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Attach API-safe response headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
