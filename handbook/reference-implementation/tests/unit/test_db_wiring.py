"""The app builds a Database and a schema readiness check from settings (no connection is made)."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from rag_service.core.config import Settings
from rag_service.db.database import Database
from rag_service.main import create_app

REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"


def test_database_and_schema_check_are_wired_from_settings() -> None:
    app = create_app(
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            database_url=SecretStr("postgresql://u:p@127.0.0.1:1/db"),
            migrations_dir=REAL,
        ),
        configure_logs=False,
    )
    assert isinstance(app.state.database, Database)
    names = [c.name for c in app.state.health_service._checks]
    assert names == ["postgres", "schema"]


def test_no_database_url_means_no_database_and_no_checks() -> None:
    app = create_app(Settings(_env_file=None), configure_logs=False)  # type: ignore[call-arg]
    assert app.state.database is None and app.state.health_service._checks == []


def test_missing_migrations_directory_skips_the_schema_check_but_keeps_connectivity(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            database_url=SecretStr("postgresql://u:p@127.0.0.1:1/db"),
            migrations_dir=tmp_path / "nope",
        ),
        configure_logs=False,
    )
    assert [c.name for c in app.state.health_service._checks] == ["postgres"]
