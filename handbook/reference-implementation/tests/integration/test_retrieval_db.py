"""Hybrid retrieval on real PostgreSQL + pgvector (component 7, ADR-004, ADR-019).

STATUS: AUTHORED, NOT EXECUTED (no database was available). The fake embedding provider produces
hash-derived vectors, so these tests prove visibility rules and plumbing, NOT semantic retrieval quality.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import UUID

import pytest
from pg import requires_pg_roles
from pydantic import SecretStr
from test_chunk_pipeline import MD, Env
from test_chunk_pipeline import env as env  # fixture re-export
from test_embeddings_db import DOC, Stack
from test_embeddings_db import stack as stack  # fixture re-export

from rag_service.core.events import LoggingEventSink
from rag_service.db.database import Database
from rag_service.db.identity import Identity
from rag_service.features.retrieval.service import HybridSearch, RetrievalConfig

pytestmark = [pytest.mark.integration, requires_pg_roles]


@pytest.fixture
def app_db(env: Env) -> Iterator[Database]:
    db = Database(
        SecretStr(env.db.app_url),
        min_size=1,
        max_size=3,
        acquire_timeout_s=5,
        statement_timeout_ms=30_000,
        idle_in_transaction_timeout_ms=15_000,
    )
    db.open()
    try:
        yield db
    finally:
        db.close()


def searcher(app_db: Database, stack: Stack, *, with_gateway: bool = True) -> HybridSearch:
    return HybridSearch(
        app_db,
        stack.gateway if with_gateway else None,
        RetrievalConfig(),
        LoggingEventSink(),
    )


def ingest(env: Env, stack: Stack, tenant: UUID, acl: tuple[str, ...] = ("eng",)) -> UUID:
    rig = env.rig(embedder=stack.embedder)
    doc, _ = env.seed(rig, tenant, DOC, MD, acl=acl)
    env.runner(rig).run_once()
    return doc


def who(tenant: UUID, *groups: str) -> Identity:
    return Identity(tenant_id=tenant, user_id="u1", groups=groups)


def test_an_ingested_document_is_found_by_both_legs(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    doc = ingest(env, stack, t)
    result = asyncio.run(searcher(app_db, stack).search(who(t, "eng"), "twenty days leave"))
    assert result.legs_used == ["fts", "vector"] and result.degraded == []
    assert result.hits and result.hits[0].candidate.document_id == doc
    assert "twenty days" in result.hits[0].candidate.content


def test_search_works_lexically_when_the_query_cannot_be_embedded(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    ingest(env, stack, t)
    result = asyncio.run(
        searcher(app_db, stack, with_gateway=False).search(who(t, "eng"), "receipts")
    )
    assert result.legs_used == ["fts"] and result.degraded == ["vector:not_configured"]
    assert result.hits and "receipts" in result.hits[0].candidate.content


def test_another_tenant_never_sees_the_chunks(env: Env, stack: Stack, app_db: Database) -> None:
    a, b = env.tenant(), env.tenant()
    ingest(env, stack, a)
    result = asyncio.run(searcher(app_db, stack).search(who(b, "eng"), "twenty days leave"))
    assert result.hits == [], "same group name, different tenant"


def test_a_caller_outside_the_acl_gets_nothing_on_either_leg(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    ingest(env, stack, t, acl=("hr",))
    result = asyncio.run(searcher(app_db, stack).search(who(t, "eng"), "twenty days leave"))
    assert result.hits == [] and result.candidates == {"fts": 0, "vector": 0}


@pytest.mark.parametrize("state", ["staged", "superseded", "failed"])
def test_only_active_versions_are_retrievable(
    env: Env, stack: Stack, app_db: Database, state: str
) -> None:
    t = env.tenant()
    doc = ingest(env, stack, t)
    env.admin.execute(
        "UPDATE rag.document_versions SET state = %s WHERE document_id = %s", (state, doc)
    )
    result = asyncio.run(searcher(app_db, stack).search(who(t, "eng"), "twenty days leave"))
    assert result.hits == [], f"a {state} version must not be a candidate"


def test_a_query_with_search_operators_and_quotes_does_not_break_the_lexical_leg(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    ingest(env, stack, t)
    hostile = "\"unbalanced ' OR 1=1; -- & | ! ( leave"
    result = asyncio.run(searcher(app_db, stack).search(who(t, "eng"), hostile))
    assert result.legs_used  # answered without an error; results are not asserted
