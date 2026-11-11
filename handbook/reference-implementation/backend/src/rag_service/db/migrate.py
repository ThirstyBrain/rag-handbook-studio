"""Forward-only SQL migrations with checksums, an advisory lock and one transaction per migration.

Files: ``NNNN_snake_case_name.sql`` (four digits, contiguous from 0001). Run as the *owner* role.
Rules enforced:
- an applied migration must still exist and its checksum must be unchanged (edits to history are errors);
- new migrations must have a higher version than every applied one (no out-of-order merges);
- two runners at once are serialised by an advisory lock, so each migration is applied exactly once;
- a failing migration rolls back completely and is not recorded.

CLI: ``python -m rag_service.db.migrate`` (uses RAG_MIGRATION_DATABASE_URL) or ``--check`` to report.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from rag_service.core.config import Settings

_log = logging.getLogger(__name__)
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
LOCK_KEY = 7_283_501  # arbitrary application-wide constant for pg_advisory_lock

_BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS rag;
CREATE TABLE IF NOT EXISTS rag.schema_migrations (
  version     integer     PRIMARY KEY,
  name        text        NOT NULL,
  checksum    text        NOT NULL,
  applied_at  timestamptz NOT NULL DEFAULT now(),
  applied_by  text        NOT NULL DEFAULT current_user
);
"""


class MigrationError(Exception):
    """A migration problem that must stop the deployment. Messages never include SQL text."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str


def discover(directory: Path) -> list[Migration]:
    if not directory.is_dir():
        raise MigrationError(f"migrations directory not found: {directory}")
    found: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _NAME.fullmatch(path.name)
        if not match:
            raise MigrationError(f"invalid migration file name: {path.name}")
        text = path.read_text(encoding="utf-8")
        found.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                sql=text,
                checksum=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    versions = [m.version for m in found]
    if len(set(versions)) != len(versions):
        raise MigrationError("duplicate migration version numbers")
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError("migration versions must be contiguous starting at 0001")
    return found


def expected_version(directory: Path) -> int:
    migrations = discover(directory)
    return migrations[-1].version if migrations else 0


def _applied(conn: psycopg.Connection) -> dict[int, tuple[str, str]]:
    rows = conn.execute("SELECT version, name, checksum FROM rag.schema_migrations").fetchall()
    return {int(v): (str(n), str(c)) for v, n, c in rows}


def migrate(dsn: str, directory: Path) -> list[Migration]:
    """Apply pending migrations and return them. Safe to run concurrently and repeatedly."""
    migrations = discover(directory)
    applied_now: list[Migration] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(_BOOTSTRAP)
            applied = _applied(conn)
            by_version = {m.version: m for m in migrations}
            for version, (name, checksum) in applied.items():
                local = by_version.get(version)
                if local is None:
                    raise MigrationError(f"applied migration {version:04d}_{name} has no file")
                if local.checksum != checksum:
                    raise MigrationError(
                        f"migration {version:04d}_{name} was modified after it was applied"
                    )
            highest = max(applied, default=0)
            for migration in migrations:
                if migration.version <= highest:
                    continue
                try:
                    with conn.transaction():
                        conn.execute(migration.sql)
                        conn.execute(
                            "INSERT INTO rag.schema_migrations (version, name, checksum) "
                            "VALUES (%s, %s, %s)",
                            (migration.version, migration.name, migration.checksum),
                        )
                except psycopg.Error as exc:
                    raise MigrationError(
                        f"migration {migration.version:04d}_{migration.name} failed "
                        f"({type(exc).__name__}); it was rolled back"
                    ) from None
                applied_now.append(migration)
                _log.info(
                    "migration_applied",
                    extra={"ctx": {"version": migration.version, "name": migration.name}},
                )
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    return applied_now


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    settings = Settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")
    if settings.migration_database_url is None:
        print("RAG_MIGRATION_DATABASE_URL is not set", file=sys.stderr)
        return 2
    try:
        if "--check" in args:
            with psycopg.connect(settings.migration_database_url.get_secret_value()) as conn:
                exists = conn.execute("SELECT to_regclass('rag.schema_migrations')").fetchone()
                current = 0
                if exists and exists[0]:
                    row = conn.execute("SELECT max(version) FROM rag.schema_migrations").fetchone()
                    current = int(row[0] or 0) if row else 0
            expected = expected_version(settings.migrations_dir)
            print(f"database at {current}, files at {expected}")
            return 0 if current == expected else 1
        done = migrate(settings.migration_database_url.get_secret_value(), settings.migrations_dir)
    except MigrationError as exc:
        print(f"migration error: {exc}", file=sys.stderr)
        return 1
    print(f"applied {len(done)} migration(s): {[f'{m.version:04d}_{m.name}' for m in done]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
