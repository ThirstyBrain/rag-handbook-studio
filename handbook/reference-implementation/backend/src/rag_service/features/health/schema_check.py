"""Readiness: is the database schema at the version this build expects?

Prevents routing traffic to a new build before its migration ran, or to an old build after the schema
moved on. Uses the application role (which may read rag.schema_migrations, nothing more).
"""

from __future__ import annotations

import asyncio
import math

import psycopg
from pydantic import SecretStr


class SchemaVersionCheck:
    name = "schema"

    def __init__(self, database_url: SecretStr, *, expected_version: int, timeout_s: float) -> None:
        self._dsn = database_url
        self._expected = expected_version
        self._connect_timeout = max(1, math.ceil(timeout_s))

    def _probe(self) -> None:
        with psycopg.connect(
            self._dsn.get_secret_value(), connect_timeout=self._connect_timeout
        ) as conn:
            row = conn.execute("SELECT max(version) FROM rag.schema_migrations").fetchone()
        current = int(row[0] or 0) if row else 0
        if current != self._expected:
            raise RuntimeError("schema version mismatch")

    async def run(self) -> None:
        await asyncio.to_thread(self._probe)
