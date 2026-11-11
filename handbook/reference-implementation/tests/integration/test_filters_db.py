"""Metadata filtering and recall under filtering on real PostgreSQL + pgvector (component 8, ADR-009).

STATUS: AUTHORED, NOT EXECUTED (no database was available). The recall test uses SYNTHETIC random vectors on
one host; its numbers are not a benchmark and say nothing about real embeddings. The ``>= 0.9`` floor is my
own threshold, set from the ADR-009 measurement (10/10 at a 10% filter with iterative scans) and must be
re-derived from a real run before it is trusted.
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from pg import requires_pg_roles
from pydantic import SecretStr
from test_chunk_pipeline import MD, Env
from test_chunk_pipeline import env as env  # fixture re-export
from test_embeddings_db import DOC, Stack
from test_embeddings_db import stack as stack  # fixture re-export

from rag_service.core.events import LoggingEventSink
from rag_service.db.database import Conn, Database
from rag_service.db.identity import Identity
from rag_service.features.indexing.ddl import VectorIndexSpec
from rag_service.features.indexing.manage import ensure_index
from rag_service.features.retrieval.filters import Condition, compile_filters
from rag_service.features.retrieval.repository import vector_candidates
from rag_service.features.retrieval.service import HybridSearch, RetrievalConfig

pytestmark = [pytest.mark.integration, requires_pg_roles]

DIMS = 16
DOCS = 10
CHUNKS_PER_DOC = 150
K = 10


@pytest.fixture
def app_db(env: Env) -> Iterator[Database]:
    db = Database(
        SecretStr(env.db.app_url),
        min_size=1,
        max_size=3,
        acquire_timeout_s=5,
        statement_timeout_ms=60_000,
        idle_in_transaction_timeout_ms=30_000,
    )
    db.open()
    try:
        yield db
    finally:
        db.close()


def who(tenant: UUID) -> Identity:
    return Identity(tenant_id=tenant, user_id="u1", groups=("eng",))


def search_service(app_db: Database, stack: Stack) -> HybridSearch:
    return HybridSearch(app_db, stack.gateway, RetrievalConfig(), LoggingEventSink())


def ingest(env: Env, stack: Stack, tenant: UUID, text: bytes = DOC) -> UUID:
    rig = env.rig(embedder=stack.embedder)
    doc, _ = env.seed(rig, tenant, text, MD)
    env.runner(rig).run_once()
    return doc


# ------------------------------------------------------------------ filters narrow, never widen


def test_a_document_filter_returns_only_that_document(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    first = ingest(env, stack, t)
    second = ingest(env, stack, t, b"# Other\n\n## Leave\n\nContractors receive five days leave.\n")
    service = search_service(app_db, stack)
    both = asyncio.run(service.search(who(t), "leave"))
    assert {h.candidate.document_id for h in both.hits} == {first, second}
    only = asyncio.run(
        service.search(
            who(t), "leave", filters=[Condition(field="document_id", op="eq", value=str(second))]
        )
    )
    assert {h.candidate.document_id for h in only.hits} == {second}


def test_a_filter_naming_another_tenants_document_returns_nothing(
    env: Env, stack: Stack, app_db: Database
) -> None:
    a, b = env.tenant(), env.tenant()
    doc_b = ingest(env, stack, b)
    ingest(env, stack, a)
    result = asyncio.run(
        search_service(app_db, stack).search(
            who(a), "leave", filters=[Condition(field="document_id", op="eq", value=str(doc_b))]
        )
    )
    assert result.hits == []


def test_timestamp_and_classification_filters_apply(
    env: Env, stack: Stack, app_db: Database
) -> None:
    t = env.tenant()
    doc = ingest(env, stack, t)
    env.admin.execute(
        "UPDATE rag.documents SET classification = 'restricted' WHERE document_id = %s", (doc,)
    )
    service = search_service(app_db, stack)
    hit = asyncio.run(
        service.search(
            who(t),
            "leave",
            filters=[Condition(field="classification", op="eq", value="restricted")],
        )
    )
    miss = asyncio.run(
        service.search(
            who(t), "leave", filters=[Condition(field="classification", op="eq", value="public")]
        )
    )
    future = asyncio.run(
        service.search(
            who(t),
            "leave",
            filters=[Condition(field="updated_at", op="gte", value="2999-01-01T00:00:00+00:00")],
        )
    )
    assert hit.hits and miss.hits == [] and future.hits == []


# ------------------------------------------------------------------ recall under filtering (ADR-009)


def _unit_vector(rng: random.Random) -> list[float]:
    raw = [rng.gauss(0, 1) for _ in range(DIMS)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def _load_synthetic(env: Env, tenant: UUID, space: str, rng: random.Random) -> list[UUID]:
    """DOCS documents x CHUNKS_PER_DOC active chunks with random unit vectors, inserted as the admin."""
    doc_ids: list[UUID] = []
    for d in range(DOCS):
        row = env.admin.execute(
            "INSERT INTO rag.documents (tenant_id, source_id, title, acl_groups) "
            "VALUES (%s, %s, %s, ARRAY['eng']) RETURNING document_id",
            (tenant, f"synthetic/{d}", f"doc {d}"),
        ).fetchone()
        assert row
        doc = row[0]
        doc_ids.append(doc)
        env.admin.execute(
            "INSERT INTO rag.document_versions (tenant_id, document_id, version, content_sha256, "
            "raw_object_uri, extractor, state) VALUES (%s, %s, 1, %s, 'none', 'synthetic', 'active')",
            (tenant, doc, uuid4().hex + uuid4().hex),
        )
        for n in range(CHUNKS_PER_DOC):
            chunk = uuid4()
            env.admin.execute(
                "INSERT INTO rag.chunks (tenant_id, chunk_id, document_id, version, ordinal, content, "
                "acl_groups) VALUES (%s, %s, %s, 1, %s, %s, ARRAY['eng'])",
                (tenant, chunk, doc, n, f"synthetic chunk {d}-{n}"),
            )
            vector = "[" + ",".join(repr(x) for x in _unit_vector(rng)) + "]"
            env.admin.execute(
                "INSERT INTO rag.chunk_embeddings (tenant_id, chunk_id, embedding_space, model, recipe, "
                "dimensions, embedding) VALUES (%s, %s, %s, 'synthetic', 'none', %s, %s::vector)",
                (tenant, chunk, space, DIMS, vector),
            )
    env.admin.execute("ANALYZE rag.chunks")
    env.admin.execute("ANALYZE rag.chunk_embeddings")
    return doc_ids


def _top_ids(
    app_db: Database,
    tenant: UUID,
    spec: VectorIndexSpec,
    query: list[float],
    only_doc: UUID,
    *,
    exact: bool,
    iterative: str,
) -> set[UUID]:
    flt = compile_filters([Condition(field="document_id", op="eq", value=str(only_doc))])

    def work(conn: Conn) -> set[UUID]:
        if exact:  # no index scan: a sequential scan gives the true nearest neighbours
            conn.execute("SET LOCAL enable_indexscan = off")
            conn.execute("SET LOCAL enable_bitmapscan = off")
        found = vector_candidates(
            conn, spec, query, K, ef_search=40, iterative_scan=iterative, flt=flt
        )
        return {c.chunk_id for c in found}

    return app_db.run_sync(who(tenant), work)


def test_recall_with_a_ten_percent_filter_stays_high_with_iterative_scans(
    env: Env, app_db: Database
) -> None:
    """Approximate filtered search versus an exact scan, over several random queries (synthetic data)."""
    rng = random.Random(20261110)  # noqa: S311 - seeded, deterministic test data
    tenant, space = env.tenant(), "synthetic-v1"
    docs = _load_synthetic(env, tenant, space, rng)
    spec = VectorIndexSpec(space=space, dimensions=DIMS)
    ensure_index(env.db.owner_url, spec)
    env.admin.execute("ANALYZE rag.chunk_embeddings")

    recalls: list[float] = []
    for _ in range(10):
        query = _unit_vector(rng)
        target = rng.choice(docs)  # each document is 10% of the tenant's chunks
        truth = _top_ids(app_db, tenant, spec, query, target, exact=True, iterative="off")
        approx = _top_ids(
            app_db, tenant, spec, query, target, exact=False, iterative="relaxed_order"
        )
        assert len(truth) == K, "the filtered exact scan must return k results"
        recalls.append(len(truth & approx) / K)
    mean = sum(recalls) / len(recalls)
    print(
        f"recall@{K} under a 10% filter (synthetic, iterative scan): mean={mean:.3f} min={min(recalls):.1f}"
    )
    assert mean >= 0.9, f"filtered recall collapsed: {recalls}"
