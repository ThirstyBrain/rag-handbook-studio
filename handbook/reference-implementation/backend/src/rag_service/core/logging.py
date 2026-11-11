"""Structured JSON logging with request correlation and secret redaction.

Rules (CLAUDE.md section 10.3): never log secrets, prompts or document text. Callers pass structured
context via ``extra={"ctx": {...}}``; keys that look sensitive are masked before output.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE_KEY = re.compile(
    r"pass(word)?|secret|token|authorization|api[_-]?key|dsn|database_url|cookie", re.I
)
REDACTED = "[REDACTED]"


def set_request_id(value: str | None) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)(?P<user>[^:/@\s]*):(?P<password>[^@\s]+)@"
)
_KV_PASSWORD = re.compile(r"(?i)\b(password|passwd|pwd)\s*=\s*[^\s&;]+")


def scrub(text: str) -> str:
    """Mask credentials in free text: ``scheme://user:pw@host`` URLs and ``password=...`` pairs.

    Exception messages from drivers can contain connection strings, which key-based redaction
    cannot see.
    """
    text = _URL_CREDENTIALS.sub(lambda m: f"{m['scheme']}{m['user']}:{REDACTED}@", text)
    return _KV_PASSWORD.sub(lambda m: f"{m[1]}={REDACTED}", text)


def redact(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with values of sensitive-looking keys masked (recursively for mappings)."""
    out: dict[str, Any] = {}
    for key, value in values.items():
        if _SENSITIVE_KEY.search(key):
            out[key] = REDACTED
        elif isinstance(value, Mapping):
            out[key] = redact(value)
        else:
            out[key] = value
    return out


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "message": scrub(record.getMessage()),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, Mapping):
            payload.update(redact(ctx))
        if record.exc_info:
            payload["exception"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str, *, json_output: bool, service_name: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter(service_name))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn's access log would duplicate ours and could include query strings.
    logging.getLogger("uvicorn.access").disabled = True
