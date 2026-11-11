"""Unit tests: configuration, logging/redaction, error model, request middleware."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from rag_service.core.config import Settings
from rag_service.core.logging import (
    REDACTED,
    JsonFormatter,
    redact,
    reset_request_id,
    set_request_id,
)
from tests_types import ClientFor, MakeApp

# ---------------------------------------------------------------- config


def test_defaults_are_safe() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "local" and s.database_url is None
    assert s.expose_api_docs is False and s.log_json is True


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_ENVIRONMENT", "production")
    monkeypatch.setenv("RAG_READINESS_CHECK_TIMEOUT_S", "5")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.is_production and s.readiness_check_timeout_s == 5


def test_invalid_values_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("RAG_LOG_LEVEL", "INFO")
    monkeypatch.setenv("RAG_READINESS_CHECK_TIMEOUT_S", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_database_url_secret_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_DATABASE_URL", "postgresql://u:hunter2@h/db")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "hunter2" not in repr(s) and "hunter2" not in str(s)
    assert s.database_url is not None and "hunter2" in s.database_url.get_secret_value()


# ---------------------------------------------------------------- logging


def test_redact_masks_sensitive_keys_recursively() -> None:
    out = redact(
        {"user": "a", "password": "x", "nested": {"api_key": "y", "ok": 1}, "database_url": "z"}
    )
    assert out == {
        "user": "a",
        "password": REDACTED,
        "nested": {"api_key": REDACTED, "ok": 1},
        "database_url": REDACTED,
    }


def test_json_formatter_has_request_id_and_redacts() -> None:
    fmt = JsonFormatter("svc")
    token = set_request_id("req-123")
    try:
        record = logging.LogRecord("n", logging.INFO, __file__, 1, "hello", None, None)
        record.ctx = {"database_url": "postgresql://u:hunter2@h/db", "status": 200}  # type: ignore[attr-defined]
        line = fmt.format(record)
    finally:
        reset_request_id(token)
    data = json.loads(line)
    assert data["request_id"] == "req-123" and data["service"] == "svc" and data["status"] == 200
    assert data["database_url"] == REDACTED and "hunter2" not in line


def test_scrub_masks_credentials_in_free_text() -> None:
    from rag_service.core.logging import scrub

    text = "connect failed: postgresql://app:hunter2@db.internal:5432/rag and password=abc123 retry"
    out = scrub(text)
    assert "hunter2" not in out and "abc123" not in out
    assert (
        "postgresql://app:[REDACTED]@db.internal:5432/rag" in out and "password=[REDACTED]" in out
    )
    assert (
        scrub("nothing sensitive at http://example.com/path")
        == "nothing sensitive at http://example.com/path"
    )


def test_exception_text_in_logs_is_scrubbed() -> None:
    fmt = JsonFormatter("svc")
    try:
        raise RuntimeError("could not connect to postgresql://u:hunter2@h/db")
    except RuntimeError:
        import sys

        record = logging.LogRecord("n", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    assert "hunter2" not in fmt.format(record)


# ---------------------------------------------------------------- errors + middleware


async def test_unknown_route_is_problem_json(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app()).get("/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "not_found" and body["request_id"] == r.headers["X-Request-ID"]


async def test_app_error_maps_to_status_and_code(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app()).get("/_apperror")
    assert r.status_code == 409
    assert r.json()["code"] == "demo_conflict" and r.json()["detail"] == "client-safe detail"


async def test_validation_error_does_not_echo_input(
    make_app: MakeApp, client_for: ClientFor
) -> None:
    r = await client_for(make_app()).get("/_item/not-a-number-SECRETVALUE")
    assert r.status_code == 422
    assert "SECRETVALUE" not in r.text
    assert r.json()["errors"][0]["loc"] == ["path", "n"]


async def test_unhandled_exception_is_generic_500_with_request_id(
    make_app: MakeApp, client_for: ClientFor, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        r = await client_for(make_app()).get("/_boom")
    assert r.status_code == 500 and r.json()["code"] == "internal_error"
    assert "hunter2" not in r.text and "secret-internal-detail" not in r.text
    assert r.headers["X-Request-ID"] == r.json()["request_id"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    requests = [
        rec.ctx
        for rec in caplog.records
        if rec.name == "rag.access" and rec.getMessage() == "request"
    ]  # type: ignore[attr-defined]
    assert requests and requests[-1]["status"] == 500


async def test_safe_inbound_request_id_is_reused(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app()).get("/health/live", headers={"X-Request-ID": "trace-ABC_1.2"})
    assert r.headers["X-Request-ID"] == "trace-ABC_1.2"


@pytest.mark.parametrize("bad", ["a b", "x" * 200, "id;drop", "ünï", ""])
async def test_unsafe_inbound_request_id_is_replaced(
    bad: str, make_app: MakeApp, client_for: ClientFor
) -> None:
    r = await client_for(make_app()).get(
        "/health/live", headers={"X-Request-ID": bad.encode("latin-1", "ignore")}
    )
    assert r.headers["X-Request-ID"] != bad and len(r.headers["X-Request-ID"]) == 32


async def test_security_headers_and_no_query_in_access_log(
    make_app: MakeApp, client_for: ClientFor, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="rag.access"):
        r = await client_for(make_app()).get("/health/live?token=SECRETQUERY")
    assert (
        r.headers["Cache-Control"] == "no-store" and r.headers["Referrer-Policy"] == "no-referrer"
    )
    lines = " ".join(json.dumps(getattr(rec, "ctx", {})) for rec in caplog.records)
    assert "SECRETQUERY" not in lines and "/health/live" in lines


async def test_api_docs_hidden_by_default_and_in_production(
    make_app: MakeApp, client_for: ClientFor
) -> None:
    assert (await client_for(make_app()).get("/docs")).status_code == 404
    assert (
        await client_for(make_app(expose_api_docs=True, environment="production")).get("/docs")
    ).status_code == 404
    assert (await client_for(make_app(expose_api_docs=True)).get("/docs")).status_code == 200
