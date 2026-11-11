"""No database needed: identity validation and migration-file discovery rules."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rag_service.db.identity import MAX_GROUPS, Identity
from rag_service.db.migrate import MigrationError, discover, expected_version

REAL_MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"

# ------------------------------------------------------------------ identity


def test_identity_normalises_groups_and_serialises_json() -> None:
    ident = Identity(tenant_id=uuid4(), user_id="alice@example.com", groups=("hr", "eng", "eng"))
    assert ident.groups == ("eng", "hr") and ident.groups_json() == '["eng", "hr"]'


@pytest.mark.parametrize(
    "bad", ["", "a b", "x" * 129, "a'b", 'a"b', "a,b", "a\nb", "ünï", "a;drop"]
)
def test_identity_rejects_unsafe_values(bad: str) -> None:
    with pytest.raises(ValidationError):
        Identity(tenant_id=uuid4(), user_id=bad)
    with pytest.raises(ValidationError):
        Identity(tenant_id=uuid4(), user_id="ok", groups=(bad,))


def test_identity_limits_group_count_and_requires_uuid() -> None:
    with pytest.raises(ValidationError):
        Identity(
            tenant_id=uuid4(), user_id="ok", groups=tuple(f"g{i}" for i in range(MAX_GROUPS + 1))
        )
    with pytest.raises(ValidationError):
        Identity(tenant_id="not-a-uuid", user_id="ok")  # type: ignore[arg-type]


# ------------------------------------------------------------------ migration discovery


def write(dir_: Path, name: str, sql: str = "SELECT 1;") -> None:
    (dir_ / name).write_text(sql, encoding="utf-8")


def test_real_migrations_are_valid_and_contiguous() -> None:
    migrations = discover(REAL_MIGRATIONS)
    assert [m.version for m in migrations] == list(range(1, len(migrations) + 1))
    assert expected_version(REAL_MIGRATIONS) == len(migrations) >= 1
    assert all(len(m.checksum) == 64 for m in migrations)


def test_discovery_rejects_gaps_duplicates_bad_names_and_missing_dir(tmp_path: Path) -> None:
    write(tmp_path, "0001_a.sql")
    write(tmp_path, "0003_c.sql")
    with pytest.raises(MigrationError, match="contiguous"):
        discover(tmp_path)
    write(tmp_path, "0002_b.sql")
    assert [m.version for m in discover(tmp_path)] == [1, 2, 3]
    write(tmp_path, "0002_other.sql")
    with pytest.raises(MigrationError, match="duplicate"):
        discover(tmp_path)
    (tmp_path / "0002_other.sql").unlink()
    write(tmp_path, "4_bad.sql")
    with pytest.raises(MigrationError, match="invalid migration file name"):
        discover(tmp_path)
    with pytest.raises(MigrationError, match="not found"):
        discover(tmp_path / "missing")


def test_checksum_changes_with_content(tmp_path: Path) -> None:
    write(tmp_path, "0001_a.sql", "SELECT 1;")
    first = discover(tmp_path)[0].checksum
    write(tmp_path, "0001_a.sql", "SELECT 2;")
    assert discover(tmp_path)[0].checksum != first
