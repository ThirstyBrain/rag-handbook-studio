"""Migration runner against a real PostgreSQL (scratch databases)."""

from __future__ import annotations

import threading
from pathlib import Path

import psycopg
import pytest
from pg import requires_pg_roles, scratch_database

from rag_service.db.migrate import MigrationError, migrate

pytestmark = [pytest.mark.integration, requires_pg_roles]
REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"


def put(dir_: Path, name: str, sql: str) -> None:
    (dir_ / name).write_text(sql, encoding="utf-8")


def versions(url: str) -> list[int]:
    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute("SELECT version FROM rag.schema_migrations ORDER BY 1")]


def test_real_migrations_apply_once_and_are_idempotent() -> None:
    with scratch_database() as db:
        first = migrate(db.owner_url, REAL)
        assert [m.version for m in first] == versions(db.owner_url)
        assert migrate(db.owner_url, REAL) == []  # second run: nothing to do
        with psycopg.connect(db.admin_url) as conn:
            who = conn.execute("SELECT DISTINCT applied_by FROM rag.schema_migrations").fetchall()
        assert who == [("rag_owner",)]


def test_modified_applied_migration_is_rejected_without_leaking_sql(tmp_path: Path) -> None:
    put(tmp_path, "0001_a.sql", "CREATE TABLE rag.a (id int);")
    with scratch_database() as db:
        migrate(db.owner_url, tmp_path)
        put(tmp_path, "0001_a.sql", "CREATE TABLE rag.a (id int, secret_column int);")
        with pytest.raises(MigrationError, match="modified after it was applied") as info:
            migrate(db.owner_url, tmp_path)
        assert "secret_column" not in str(info.value)


def test_applied_migration_whose_file_disappeared_is_rejected(tmp_path: Path) -> None:
    put(tmp_path, "0001_a.sql", "CREATE TABLE rag.a (id int);")
    put(tmp_path, "0002_b.sql", "CREATE TABLE rag.b (id int);")
    with scratch_database() as db:
        migrate(db.owner_url, tmp_path)
        (tmp_path / "0002_b.sql").unlink()
        with pytest.raises(MigrationError, match="has no file"):
            migrate(db.owner_url, tmp_path)


def test_failed_migration_rolls_back_completely(tmp_path: Path) -> None:
    put(tmp_path, "0001_ok.sql", "CREATE TABLE rag.ok_table (id int);")
    put(
        tmp_path,
        "0002_bad.sql",
        "CREATE TABLE rag.half_done (id int); SELECT 1/0 /* TOP-SECRET-SQL */;",
    )
    with scratch_database() as db:
        with pytest.raises(MigrationError, match="rolled back") as info:
            migrate(db.owner_url, tmp_path)
        assert "TOP-SECRET-SQL" not in str(info.value)
        assert versions(db.owner_url) == [1]
        with psycopg.connect(db.admin_url) as conn:
            exists = conn.execute(
                "SELECT to_regclass('rag.ok_table'), to_regclass('rag.half_done')"
            ).fetchone()
        assert exists is not None and exists[0] is not None and exists[1] is None
        # fixing the file (it was never recorded) lets the next run succeed
        put(tmp_path, "0002_bad.sql", "CREATE TABLE rag.half_done (id int);")
        assert [m.version for m in migrate(db.owner_url, tmp_path)] == [2]


def test_concurrent_runners_apply_each_migration_exactly_once() -> None:
    with scratch_database() as db:
        results: list[int] = []
        errors: list[Exception] = []

        def run() -> None:
            try:
                results.append(len(migrate(db.owner_url, REAL)))
            except Exception as exc:  # pragma: no cover - failure path is asserted below
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        total = sum(results)
        assert total == len(versions(db.owner_url)) >= 1, (
            "each migration applied exactly once across runners"
        )
