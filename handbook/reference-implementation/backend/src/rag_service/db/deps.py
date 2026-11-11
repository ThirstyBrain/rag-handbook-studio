"""FastAPI dependency: how a feature obtains the tenant-scoped database."""

from __future__ import annotations

from fastapi import Request

from rag_service.core.errors import AppError
from rag_service.db.database import Database


def get_database(request: Request) -> Database:
    database: Database | None = getattr(request.app.state, "database", None)
    if database is None:
        raise AppError("database_not_configured", "No database is configured", 503)
    return database
