"""Error model: RFC 9457 problem+json responses that never leak internals or echo input values."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rag_service.core.logging import get_request_id

PROBLEM_MEDIA_TYPE = "application/problem+json"
_log = logging.getLogger(__name__)


class AppError(Exception):
    """A deliberate, client-safe error. ``code`` is a stable machine-readable identifier."""

    def __init__(
        self, code: str, title: str, status_code: int = 400, detail: str | None = None
    ) -> None:
        super().__init__(f"{code}: {title}")
        self.code = code
        self.title = title
        self.status_code = status_code
        self.detail = detail


def problem(
    status_code: int, code: str, title: str, detail: str | None = None, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:rag:error:{code}",
        "title": title,
        "status": status_code,
        "code": code,
    }
    if detail:
        body["detail"] = detail
    request_id = get_request_id()
    if request_id:
        body["request_id"] = request_id
    body.update(extra)
    return JSONResponse(body, status_code=status_code, media_type=PROBLEM_MEDIA_TYPE)


def internal_error_response() -> JSONResponse:
    return problem(500, "internal_error", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return problem(exc.status_code, exc.code, exc.title, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        title = "Resource not found" if exc.status_code == 404 else "HTTP error"
        return problem(exc.status_code, code, title)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where and what, never the offending input value.
        errors = [{"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return problem(422, "validation_error", "Request validation failed", errors=errors)
