"""Shared helpers for integration tests that need the compose PostgreSQL with its two roles.

Environment (see reference-implementation/README.md, section "Database tests"):
  RAG_TEST_ADMIN_URL       superuser DSN of the compose server (used to create scratch databases and seed data)
  RAG_TEST_OWNER_PASSWORD  password of rag_owner
  RAG_TEST_APP_PASSWORD    password of rag_app
Each test module that needs a schema gets its own scratch database, created and dropped here.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import pytest

ADMIN_URL = os.environ.get("RAG_TEST_ADMIN_URL")
OWNER_PASSWORD = os.environ.get("RAG_TEST_OWNER_PASSWORD")
APP_PASSWORD = os.environ.get("RAG_TEST_APP_PASSWORD")
WORKER_PASSWORD = os.environ.get("RAG_TEST_WORKER_PASSWORD")
ENABLED = bool(ADMIN_URL and OWNER_PASSWORD and APP_PASSWORD and WORKER_PASSWORD)
requires_pg_roles = pytest.mark.skipif(
    not ENABLED,
    reason="set RAG_TEST_ADMIN_URL, RAG_TEST_OWNER_PASSWORD, RAG_TEST_APP_PASSWORD, RAG_TEST_WORKER_PASSWORD",
)


def _with(
    url: str, *, user: str | None = None, password: str | None = None, db: str | None = None
) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = f":{parts.port}" if parts.port else ""
    creds = (
        f"{user}:{quote(password or '', safe='')}@" if user else (parts.netloc.split("@")[0] + "@")
    )
    return urlunsplit(
        (parts.scheme, f"{creds}{host}{port}", f"/{db}" if db else parts.path, "", "")
    )


@dataclass(frozen=True)
class ScratchDb:
    name: str
    admin_url: str  # superuser: seeds data, bypasses RLS
    owner_url: str  # rag_owner: runs migrations
    app_url: str  # rag_app: what the service uses
    worker_url: str  # rag_worker: the background worker (job queue only)


@contextmanager
def scratch_database() -> Iterator[ScratchDb]:
    assert ADMIN_URL and OWNER_PASSWORD and APP_PASSWORD and WORKER_PASSWORD
    name = f"rag_test_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}" OWNER rag_owner')
        admin.execute(f'REVOKE ALL ON DATABASE "{name}" FROM PUBLIC')
        admin.execute(f'GRANT CONNECT ON DATABASE "{name}" TO rag_owner, rag_app, rag_worker')
    # what the docker init script does for the real database: an administrator installs pgvector
    with psycopg.connect(_with(ADMIN_URL, db=name), autocommit=True) as scratch:
        scratch.execute("CREATE EXTENSION IF NOT EXISTS vector")
    try:
        yield ScratchDb(
            name=name,
            admin_url=_with(ADMIN_URL, db=name),
            owner_url=_with(ADMIN_URL, user="rag_owner", password=OWNER_PASSWORD, db=name),
            app_url=_with(ADMIN_URL, user="rag_app", password=APP_PASSWORD, db=name),
            worker_url=_with(ADMIN_URL, user="rag_worker", password=WORKER_PASSWORD, db=name),
        )
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
