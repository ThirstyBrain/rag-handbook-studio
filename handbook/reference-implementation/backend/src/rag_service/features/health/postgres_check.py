"""PostgreSQL readiness probe.

Uses synchronous psycopg in a worker thread so the check works on every platform's event loop
(psycopg's async API cannot run on Windows' default ProactorEventLoop) and never blocks the loop.
The connect timeout bounds the thread; the service-level timeout bounds the caller.
"""

from __future__ import annotations

import asyncio
import math

import psycopg
from pydantic import SecretStr


class PostgresCheck:
    name = "postgres"

    def __init__(self, database_url: SecretStr, *, timeout_s: float) -> None:
        self._dsn = database_url
        self._connect_timeout = max(1, math.ceil(timeout_s))

    def _probe(self) -> None:
        with (
            psycopg.connect(
                self._dsn.get_secret_value(), connect_timeout=self._connect_timeout
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SELECT 1")
            if cur.fetchone() != (1,):
                raise RuntimeError("unexpected probe result")

    async def run(self) -> None:
        await asyncio.to_thread(self._probe)
