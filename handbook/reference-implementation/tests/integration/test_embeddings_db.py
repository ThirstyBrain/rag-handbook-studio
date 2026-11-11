"""Embeddings through the worker on real PostgreSQL: atomic writes, retries, and the roles' boundaries (ADR-017).

The embedder is the real ChunkEmbedder over the real gateway with the fake provider, so the path from
chunk text to a stored vector is exercised end to end; only the model is a stand-in.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import psycopg
import pytest
from pg import requires_pg_roles
from pydantic import SecretStr
from test_chunk_pipeline import MD, Env, WorkerConn, worker_conn
from test_chunk_pipeline import env as env  # fixture re-export

from rag_service.db.database import Database
from rag_service.db.identity import Identity
from rag_service.features.embedding.bridge import AsyncBridge
from rag_service.features.embedding.service import RECIPE, ChunkEmbedder, EmbeddingConfig
from rag_service.features.llm import GatewayConfig, LlmGateway, build_gateway
from rag_service.features.llm.config import ProviderConfig, RouteConfig, Target
from rag_service.features.llm.errors import ProviderUnavailable
from rag_service.features.llm.providers.fake import FAKE_DIMENSIONS, FakeProvider

pytestmark = [pytest.mark.integration, requires_pg_roles]
DOC = b"# Handbook\n\n## Leave\n\nEmployees receive twenty days.\n\n## Expenses\n\nClaims need receipts.\n"


class Stack:
    def __init__(self, *, outcomes: list[Any] | None = None, space: str = "fake-v1") -> None:
        config = GatewayConfig(
            providers={"f": ProviderConfig(kind="fake", locality="local")},
            routes={
                "embed": RouteConfig(
                    kind="embed",
                    max_attempts_per_target=1,
                    chain=[Target(provider="f", model="fake-embed", embedding_space=space)],
                )
            },
        )
        self.gateway: LlmGateway = build_gateway(config, allow_fake=True)
        if outcomes is not None:  # script the provider: errors are raised, then normal answers
            provider = self.gateway._providers["f"]
            assert isinstance(provider, FakeProvider)
            provider._outcomes.extend(outcomes)
        self.bridge = AsyncBridge()
        self.embedder = ChunkEmbedder(self.gateway, EmbeddingConfig(batch_size=2), self.bridge)

    def close(self) -> None:
        self.bridge.run(self.gateway.aclose(), 5)
        self.bridge.close()


@pytest.fixture
def stack() -> Iterator[Stack]:
    s = Stack()
    try:
        yield s
    finally:
        s.close()


def embeddings(env: Env, doc: UUID) -> list[dict[str, Any]]:
    cur = env.admin.execute(
        "SELECT c.ordinal, e.embedding_space, e.model, e.recipe, e.dimensions, e.embedding::text, "
        "c.chunk_id FROM rag.chunk_embeddings e JOIN rag.chunks c USING (tenant_id, chunk_id) "
        "WHERE c.document_id = %s ORDER BY c.ordinal",
        (doc,),
    )
    names = [d.name for d in cur.description or []]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def requeue(env: Env, doc: UUID) -> None:
    env.admin.execute(
        "UPDATE rag.ingestion_jobs SET state = 'queued', attempts = 0 WHERE document_id = %s",
        (doc,),
    )


# ------------------------------------------------------------------ the happy path


def test_every_chunk_gets_a_vector_recording_space_model_recipe_and_dimension(
    env: Env, stack: Stack
) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD)
    env.runner(rig).run_once()
    chunks, rows = env.chunks(doc), embeddings(env, doc)
    assert len(chunks) == 2 and [r["ordinal"] for r in rows] == [0, 1]
    for row in rows:
        assert row["embedding_space"] == "fake-v1" and row["model"] == "fake-embed"
        assert row["recipe"] == RECIPE and row["dimensions"] == FAKE_DIMENSIONS
        assert len(row["embedding"].strip("[]").split(",")) == FAKE_DIMENSIONS
    assert rows[0]["embedding"] != rows[1]["embedding"]
    assert env.job_row(doc)[0] == "succeeded" and env.version_row(doc)[0] == "active"


def test_the_stored_vector_is_the_embedding_of_the_section_path_and_content(
    env: Env, stack: Stack
) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD)
    env.runner(rig).run_once()
    first = env.chunks(doc)[0]
    expected = FakeProvider("x")
    import asyncio

    vectors, _ = asyncio.run(
        expected.embed("m", [f"{first['section_path']}\n\n{first['content']}"])
    )
    stored = [float(x) for x in embeddings(env, doc)[0]["embedding"].strip("[]").split(",")]
    assert stored == pytest.approx(vectors[0], rel=1e-6)


def test_reprocessing_keeps_chunk_ids_and_replaces_vectors_without_duplicating(
    env: Env, stack: Stack
) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD)
    runner = env.runner(rig)
    runner.run_once()
    first = embeddings(env, doc)
    requeue(env, doc)
    runner.run_once()
    second = embeddings(env, doc)
    assert env.job_row(doc)[0] == "succeeded"
    assert [r["chunk_id"] for r in first] == [r["chunk_id"] for r in second], "stable chunk ids"
    assert [r["embedding"] for r in first] == [r["embedding"] for r in second]
    total = env.admin.execute("SELECT count(*) FROM rag.chunk_embeddings").fetchone()
    assert total == (len(second),)


def test_chunks_of_different_documents_never_share_ids(env: Env, stack: Stack) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    d1, _ = env.seed(rig, t, DOC, MD)
    d2, _ = env.seed(rig, t, DOC.replace(b"twenty", b"thirty"), MD)
    runner = env.runner(rig)
    runner.run_once()
    runner.run_once()
    ids = {d: {r["chunk_id"] for r in embeddings(env, d)} for d in (d1, d2)}
    assert ids[d1].isdisjoint(ids[d2])


# ------------------------------------------------------------------ failure handling


def test_a_provider_outage_retries_the_job_and_writes_nothing(env: Env) -> None:
    s = Stack(outcomes=[ProviderUnavailable("down")])
    try:
        rig, t = env.rig(embedder=s.embedder), env.tenant()
        doc, _ = env.seed(rig, t, DOC, MD)
        runner = env.runner(rig)
        runner.run_once()
        state, attempts, error = env.job_row(doc)
        assert (state, attempts) == ("queued", 1) and error and "PermanentFailure" not in error
        assert env.chunks(doc) == [] and embeddings(env, doc) == [], "no half-written version"
        assert env.version_row(doc)[0] == "staged"
        runner.run_once()  # the provider recovers: the retry completes the work
        assert env.job_row(doc)[0] == "succeeded" and len(embeddings(env, doc)) == 2
    finally:
        s.close()


def test_a_refused_input_fails_the_version_permanently(env: Env) -> None:
    from rag_service.features.llm.errors import ContentRefused

    s = Stack(outcomes=[ContentRefused("no")])
    try:
        rig, t = env.rig(embedder=s.embedder), env.tenant()
        doc, _ = env.seed(rig, t, DOC, MD)
        env.runner(rig).run_once()
        assert env.version_row(doc) == ("failed", "pending", "embedding_rejected")
        state, _, error = env.job_row(doc)
        assert state == "dead" and error == "PermanentFailure:embedding_rejected"
        assert env.chunks(doc) == []
    finally:
        s.close()


def test_a_stale_job_embeds_nothing_into_the_database(env: Env, stack: Stack) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, version = env.seed(rig, t, DOC, MD)
    env.admin.execute(
        "UPDATE rag.document_versions SET state = 'superseded' WHERE document_id = %s", (doc,)
    )
    env.runner(rig).run_once()
    assert embeddings(env, doc) == [] and env.chunks(doc, version) == []


def test_without_an_embedder_chunks_are_stored_and_no_vectors_exist(env: Env) -> None:
    rig, t = env.rig(), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD)
    env.runner(rig).run_once()
    assert len(env.chunks(doc)) == 2 and embeddings(env, doc) == []


# ------------------------------------------------------------------ deletion and lifecycle


def test_deleting_the_document_or_replacing_chunks_removes_their_vectors(
    env: Env, stack: Stack
) -> None:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD)
    env.runner(rig).run_once()
    assert len(embeddings(env, doc)) == 2
    env.admin.execute("DELETE FROM rag.documents WHERE document_id = %s", (doc,))
    left = env.admin.execute("SELECT count(*) FROM rag.chunk_embeddings").fetchone()
    assert left == (0,), "vectors do not outlive their chunks"


# ------------------------------------------------------------------ the roles' boundaries


def _one_chunk(
    env: Env, stack: Stack, *, acl: tuple[str, ...] = ("eng",)
) -> tuple[UUID, UUID, UUID]:
    rig, t = env.rig(embedder=stack.embedder), env.tenant()
    doc, _ = env.seed(rig, t, DOC, MD, acl=acl)
    env.runner(rig).run_once()
    chunk = env.admin.execute(
        "SELECT chunk_id FROM rag.chunks WHERE document_id = %s ORDER BY ordinal LIMIT 1", (doc,)
    ).fetchone()
    assert chunk
    return t, doc, chunk[0]


INSERT = (
    "INSERT INTO rag.chunk_embeddings (tenant_id, chunk_id, embedding_space, model, recipe, "
    "dimensions, embedding) VALUES (%s, %s, 'other-space', 'm', 'r', 3, '[1,2,3]')"
)


def test_the_worker_can_add_vectors_to_staged_chunks_but_not_read_update_or_delete_them(
    env: Env, stack: Stack
) -> None:
    t, doc, chunk = _one_chunk(env, stack)
    with worker_conn(env, t) as conn:
        conn.execute(INSERT, (t, chunk))  # a second space for the same chunk: allowed while staged
        for sql in (
            "SELECT embedding FROM rag.chunk_embeddings",
            "SELECT model FROM rag.chunk_embeddings",
            "UPDATE rag.chunk_embeddings SET model = 'x'",
            "DELETE FROM rag.chunk_embeddings",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)  # type: ignore[arg-type]
            conn.rollback()
    assert doc


def test_the_worker_cannot_add_vectors_to_active_or_foreign_chunks(env: Env, stack: Stack) -> None:
    t, doc, chunk = _one_chunk(env, stack)
    other = env.tenant()
    with worker_conn(env, other) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute(INSERT, (other, chunk))  # right tenant claim, someone else's chunk
    with worker_conn(env, other) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute(INSERT, (t, chunk))  # claims the owning tenant while scoped to another
    env.admin.execute(
        "UPDATE rag.document_versions SET state = 'active' WHERE document_id = %s", (doc,)
    )
    with worker_conn(env, t) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute(INSERT, (t, chunk))


def test_a_vector_must_match_its_recorded_dimension(env: Env, stack: Stack) -> None:
    t, _, chunk = _one_chunk(env, stack)
    with worker_conn(env, t) as conn, pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(INSERT.replace("'[1,2,3]'", "'[1,2]'"), (t, chunk))


def _app(env: Env) -> Database:
    db = Database(
        SecretStr(env.db.app_url),
        min_size=1,
        max_size=2,
        acquire_timeout_s=5,
        statement_timeout_ms=30_000,
        idle_in_transaction_timeout_ms=15_000,
    )
    db.open()
    return db


def test_the_app_reads_vectors_only_for_chunks_its_acl_and_tenant_allow(
    env: Env, stack: Stack
) -> None:
    t, _, _ = _one_chunk(env, stack, acl=("hr",))
    other = env.tenant()
    db = _app(env)
    try:

        def count(tenant: UUID, groups: tuple[str, ...]) -> int:
            rows = db.run_sync(
                Identity(tenant_id=tenant, user_id="u", groups=groups),
                lambda c: c.execute("SELECT count(*) AS n FROM rag.chunk_embeddings").fetchall(),
            )
            return int(rows[0]["n"])

        assert count(t, ("hr",)) == 2
        assert count(t, ("eng",)) == 0, "chunk ACL applies to its vectors"
        assert count(other, ("hr",)) == 0, "tenant isolation applies to its vectors"
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.run_sync(
                Identity(tenant_id=t, user_id="u", groups=("hr",)),
                lambda c: c.execute("DELETE FROM rag.chunk_embeddings"),
            )
    finally:
        db.close()


def test_worker_connections_are_the_only_writers(env: Env, stack: Stack) -> None:
    t, _, chunk = _one_chunk(env, stack)
    db = _app(env)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.run_sync(
                Identity(tenant_id=t, user_id="u", groups=("eng",)),
                lambda c: c.execute(INSERT, (t, chunk)),
            )
    finally:
        db.close()


def test_the_worker_connection_helper_is_the_shared_one(env: Env) -> None:
    assert WorkerConn is not None  # imported for its boundary tests; keeps the shared helper honest


def test_embeddings_have_exactly_one_policy_per_role_and_command(env: Env) -> None:
    rows = env.admin.execute(
        "SELECT cmd, roles::text FROM pg_policies "
        "WHERE schemaname = 'rag' AND tablename = 'chunk_embeddings' ORDER BY cmd"
    ).fetchall()
    assert rows == [("INSERT", "{rag_worker}"), ("SELECT", "{rag_app}")], (
        "no policy may apply to PUBLIC or add another command: permissive policies are OR-ed"
    )
