"""Integration: the real PostgreSQL probe against a running database.

Run with the compose database up and RAG_TEST_DATABASE_URL set (see the README).
Skipped, and recorded as skipped in the quality report, when the variable is absent.
"""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from rag_service.features.health.postgres_check import PostgresCheck

pytestmark = pytest.mark.integration
DSN = os.environ.get("RAG_TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(DSN is None, reason="RAG_TEST_DATABASE_URL not set")


@requires_db
async def test_probe_succeeds_against_real_database() -> None:
    assert DSN is not None
    await PostgresCheck(SecretStr(DSN), timeout_s=3).run()


async def test_probe_fails_fast_when_unreachable() -> None:
    # Port 1 on loopback refuses immediately; no external dependency is needed for this test.
    check = PostgresCheck(SecretStr("postgresql://u:p@127.0.0.1:1/db"), timeout_s=1)
    with pytest.raises(Exception):  # noqa: B017 - any driver error is acceptable; the service maps it to "unavailable"
        await check.run()


@requires_db
async def test_pgvector_extension_available() -> None:
    import psycopg

    assert DSN is not None
    with psycopg.connect(DSN, connect_timeout=3) as conn:
        row = conn.execute(
            "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone()
    assert row == (1,)
