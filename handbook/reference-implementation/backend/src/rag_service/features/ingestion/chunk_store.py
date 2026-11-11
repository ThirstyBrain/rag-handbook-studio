"""The worker's write path for chunks (ADR-016), as the rag_worker role.

The identity set on each transaction names only the tenant of the job being processed. The database
(migration 0003) then lets the worker touch only STAGED versions of that tenant: it can replace a
version's chunks, mark the version failed and (migration 0005) activate a version that has chunks, but
cannot read chunk content or reach another tenant. Chunks inherit the document's ACL at write time, read in the same transaction.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Literal
from uuid import UUID, uuid5

from psycopg.errors import UniqueViolation

from rag_service.db.database import Conn, Database
from rag_service.db.identity import Identity
from rag_service.features.chunking.chunker import Chunk
from rag_service.features.embedding.service import EmbeddedChunks

WorkerOutcome = Literal["written", "stale"]
ActivationOutcome = Literal["activated", "stale"]


class _NotActivated(Exception):
    """Raised inside the activation transaction to roll it back when the version was not staged."""


_WORKER_USER = "worker"
# Fixed namespace for derived chunk ids; changing it changes every chunk id.
_CHUNK_NAMESPACE = UUID("6f0c2d4e-5a1b-4c3d-9e8f-7a6b5c4d3e2f")


def chunk_id_for(tenant_id: UUID, document_id: UUID, version: int, chunk: Chunk) -> UUID:
    """Derived chunk identity (ADR-003): the same content at the same place gets the same id when a
    version is re-processed, so citations and embeddings can be matched across re-runs. The worker has
    no right to read ids back, so it generates them rather than relying on RETURNING."""
    digest = hashlib.sha256(chunk.content.encode()).hexdigest()[:32]
    return uuid5(_CHUNK_NAMESPACE, f"{tenant_id}:{document_id}:{version}:{chunk.ordinal}:{digest}")


def vector_literal(vector: Sequence[float]) -> str:
    """pgvector text input format. Values were checked finite by the embedder, so no escaping is needed."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _identity(tenant_id: UUID) -> Identity:
    return Identity(tenant_id=tenant_id, user_id=_WORKER_USER, groups=())


class ChunkStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def replace_chunks(
        self,
        tenant_id: UUID,
        document_id: UUID,
        version: int,
        chunks: Sequence[Chunk],
        *,
        extractor: str,
        chunker: str,
        embeddings: EmbeddedChunks | None = None,
    ) -> WorkerOutcome:
        """Idempotently store the chunks (and their embeddings) of one staged version, all or nothing.

        Returns "stale" when the version is no longer staged or the document was deleted: the job's
        work is no longer wanted and nothing is written."""

        if embeddings is not None and len(embeddings.vectors) != len(chunks):
            raise ValueError("one embedding per chunk is required")
        ids = [chunk_id_for(tenant_id, document_id, version, c) for c in chunks]

        def work(conn: Conn) -> WorkerOutcome:
            row = conn.execute(
                "SELECT d.acl_groups FROM rag.documents d "
                "JOIN rag.document_versions v "
                "  ON v.tenant_id = d.tenant_id AND v.document_id = d.document_id "
                "WHERE d.tenant_id = %s AND d.document_id = %s AND d.status = 'active' "
                "AND v.version = %s AND v.state = 'staged'",
                (tenant_id, document_id, version),
            ).fetchone()
            if row is None:
                return "stale"
            acl = list(row["acl_groups"])
            conn.execute(
                "DELETE FROM rag.chunks WHERE tenant_id = %s AND document_id = %s AND version = %s",
                (tenant_id, document_id, version),
            )
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO rag.chunks (chunk_id, tenant_id, document_id, version, ordinal, "
                    "content, section_path, token_count, acl_groups, page_start, page_end, chunker) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (
                            chunk_id,
                            tenant_id,
                            document_id,
                            version,
                            c.ordinal,
                            c.content,
                            c.section_path,
                            c.token_count,
                            acl,
                            c.page_start,
                            c.page_end,
                            chunker,
                        )
                        for chunk_id, c in zip(ids, chunks, strict=True)
                    ],
                )
                if embeddings is not None:
                    cur.executemany(
                        "INSERT INTO rag.chunk_embeddings (tenant_id, chunk_id, embedding_space, "
                        "model, recipe, dimensions, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                        [
                            (
                                tenant_id,
                                chunk_id,
                                embeddings.space,
                                model,
                                embeddings.recipe,
                                embeddings.dimensions,
                                vector_literal(vector),
                            )
                            for chunk_id, model, vector in zip(
                                ids, embeddings.models, embeddings.vectors, strict=True
                            )
                        ],
                    )
            conn.execute(
                "UPDATE rag.document_versions SET extractor = %s "
                "WHERE tenant_id = %s AND document_id = %s AND version = %s",
                (extractor, tenant_id, document_id, version),
            )
            return "written"

        return self._db.run_sync(_identity(tenant_id), work)

    def activate_version(
        self, tenant_id: UUID, document_id: UUID, version: int
    ) -> ActivationOutcome:
        """Make a complete staged version the document's single active version (ADR-019, migration 0005).

        In one transaction: older active versions become superseded, then this one becomes active. The
        database refuses activation of a version without chunks and a second active version per document.
        Returns "stale" (and changes nothing) when the version is no longer staged, or when a newer
        version is already active; the caller treats that as work that is no longer wanted."""

        def work(conn: Conn) -> ActivationOutcome:
            conn.execute(
                "UPDATE rag.document_versions SET state = 'superseded' "
                "WHERE tenant_id = %s AND document_id = %s AND state = 'active' AND version < %s",
                (tenant_id, document_id, version),
            )
            activated: int = conn.execute(
                "UPDATE rag.document_versions SET state = 'active' "
                "WHERE tenant_id = %s AND document_id = %s AND version = %s AND state = 'staged'",
                (tenant_id, document_id, version),
            ).rowcount
            if activated != 1:
                raise _NotActivated
            return "activated"

        try:
            return self._db.run_sync(_identity(tenant_id), work)
        except _NotActivated:
            return "stale"  # the transaction rolled back, so the superseding above did not happen
        except UniqueViolation:
            return "stale"  # a newer version is already active; this older one must not replace it

    def mark_failed(self, tenant_id: UUID, document_id: UUID, version: int, reason: str) -> bool:
        """Record a permanent failure on a staged version. ``reason`` is a short safe code."""

        def work(conn: Conn) -> bool:
            updated: int = conn.execute(
                "UPDATE rag.document_versions SET state = 'failed', failure_reason = %s "
                "WHERE tenant_id = %s AND document_id = %s AND version = %s",
                (reason, tenant_id, document_id, version),
            ).rowcount
            return updated == 1

        return self._db.run_sync(_identity(tenant_id), work)
