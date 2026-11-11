"""Pooled, tenant-scoped transactions.

Design (ADR-013): synchronous psycopg and a connection pool, called from worker threads. This works on
every platform's event loop (psycopg's async API cannot run on Windows' default loop) and keeps blocking
I/O off the event loop.

Isolation rule: the caller's identity is written into the database with ``set_config(..., true)``
(transaction-local, like ``SET LOCAL``) as the first statement of every transaction, and the
database's row-level-security policies read it. Because it is transaction-local it cannot survive into
the next request that reuses the pooled connection (measured in scripts/verify-sql/03-rls.sql: a
session-level setting leaks, a transaction-local one does not).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar, cast

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import SecretStr

from rag_service.db.identity import Identity

T = TypeVar("T")
Conn = psycopg.Connection[dict[str, Any]]  # rows are dicts (row_factory=dict_row)

_SET_IDENTITY = (
    "SELECT set_config('app.tenant_id', %s, true), "
    "set_config('app.user_id', %s, true), "
    "set_config('app.groups', %s, true)"
)


class Database:
    def __init__(
        self,
        dsn: SecretStr,
        *,
        min_size: int,
        max_size: int,
        acquire_timeout_s: float,
        statement_timeout_ms: int,
        idle_in_transaction_timeout_ms: int,
    ) -> None:
        options = (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c idle_in_transaction_session_timeout={idle_in_transaction_timeout_ms}"
        )
        self._pool: ConnectionPool[Any] = ConnectionPool(
            dsn.get_secret_value(),
            min_size=min_size,
            max_size=max_size,
            timeout=acquire_timeout_s,
            kwargs={"row_factory": dict_row, "options": options},
            open=False,
        )

    def open(self) -> None:
        # wait=False: the service starts even if the database is down; readiness reports it.
        self._pool.open(wait=False)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(self, identity: Identity) -> Iterator[Conn]:
        """One transaction scoped to ``identity``; commits on success, rolls back on any exception."""
        with self._pool.connection() as conn:
            conn.execute(
                _SET_IDENTITY,
                (str(identity.tenant_id), identity.user_id, identity.groups_json()),
            )
            yield cast(Conn, conn)

    def run_sync(self, identity: Identity, work: Callable[[Conn], T]) -> T:
        with self.transaction(identity) as conn:
            return work(conn)

    async def run(self, identity: Identity, work: Callable[[Conn], T]) -> T:
        """Run ``work(conn)`` in a worker thread inside one identity-scoped transaction."""
        return await asyncio.to_thread(self.run_sync, identity, work)
