"""Readiness check: schema version must match what this build expects."""

from __future__ import annotations

from pathlib import Path

import pytest
from pg import requires_pg_roles, scratch_database
from pydantic import SecretStr

from rag_service.db.migrate import expected_version, migrate
from rag_service.features.health.schema_check import SchemaVersionCheck

pytestmark = [pytest.mark.integration, requires_pg_roles]
REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"


async def test_schema_check_passes_only_at_the_expected_version() -> None:
    expected = expected_version(REAL)
    with scratch_database() as db:
        dsn = SecretStr(db.app_url)
        # before any migration the table does not exist: not ready
        with pytest.raises(Exception):  # noqa: B017 - any driver error means "not ready"
            await SchemaVersionCheck(dsn, expected_version=expected, timeout_s=3).run()
        migrate(db.owner_url, REAL)
        await SchemaVersionCheck(dsn, expected_version=expected, timeout_s=3).run()
        # a build expecting a newer schema than the database has is not ready
        with pytest.raises(RuntimeError, match="mismatch"):
            await SchemaVersionCheck(dsn, expected_version=expected + 1, timeout_s=3).run()
        # and a build expecting an older schema than the database has is not ready either
        with pytest.raises(RuntimeError, match="mismatch"):
            await SchemaVersionCheck(dsn, expected_version=expected - 1, timeout_s=3).run()
