"""Pure-ASGI request middleware (safe for streaming responses, unlike BaseHTTPMiddleware).

Responsibilities: request-id propagation (inbound id accepted only if it matches a safe pattern),
security headers, one access-log line per request (method, path, status, duration; no query string,
headers or body), and conversion of unhandled exceptions into a generic 500 problem response.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rag_service.core.errors import internal_error_response
from rag_service.core.logging import reset_request_id, set_request_id

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}
_log = logging.getLogger("rag.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, header_name: str, max_id_length: int) -> None:
        self.app = app
        self._header = header_name
        self._max = max_id_length

    def _request_id(self, scope: Scope) -> str:
        wanted = self._header.lower().encode("latin-1")
        for key, value in scope["headers"]:
            if key == wanted:
                candidate: str = value.decode("latin-1")
                if candidate and len(candidate) <= self._max and _SAFE_ID.fullmatch(candidate):
                    return candidate
        return uuid.uuid4().hex

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        token = set_request_id(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[self._header] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                _log.exception("unhandled_exception", extra={"ctx": {"path": scope["path"]}})
                if response_started:
                    raise
                await internal_error_response()(scope, receive, send_wrapper)
        finally:
            _log.info(
                "request",
                extra={
                    "ctx": {
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                },
            )
            reset_request_id(token)
