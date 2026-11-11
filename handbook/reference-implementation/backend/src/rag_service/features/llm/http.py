"""Maps gateway errors to safe HTTP problem responses (no provider names, models or message text)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rag_service.core.errors import problem
from rag_service.features.llm.errors import (
    AllTargetsFailed,
    BudgetExceeded,
    ContentRefused,
    InvalidRequest,
    LlmError,
    PolicyViolation,
)

# error class -> (status, stable code, client-safe title)
_MAPPING: list[tuple[type[LlmError], int, str, str]] = [
    (PolicyViolation, 403, "llm_policy_violation", "No model may process this data"),
    (BudgetExceeded, 503, "llm_budget_exceeded", "Model budget exhausted"),
    (ContentRefused, 422, "llm_refused", "The model declined to answer"),
    (AllTargetsFailed, 503, "llm_unavailable", "Language model temporarily unavailable"),
    # A bad route or malformed call is a programming/configuration error, not the caller's fault.
    (InvalidRequest, 500, "llm_invalid_request", "Internal server error"),
]


def register_llm_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LlmError)
    async def _llm_error(_: Request, exc: LlmError) -> JSONResponse:
        for cls, status, code, title in _MAPPING:
            if isinstance(exc, cls):
                return problem(status, code, title)
        return problem(502, "llm_error", "Language model error")
