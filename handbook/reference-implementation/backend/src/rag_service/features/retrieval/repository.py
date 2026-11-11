"""Candidate queries for the two retrieval legs, run as rag_app inside a tenant-scoped transaction.

Every query applies the same visibility rules, in the query and not after it (ADR-004, ADR-009):
  * tenant: row-level security is the boundary; ``tenant_id = rag.app_tenant()`` is repeated for plan
    friendliness (defence in depth, not a replacement);
  * ACL: ``acl_groups && rag.app_groups()`` on the chunk;
  * lifecycle: the chunk's version is ``active`` and its document is ``active`` (ADR-019), so staged,
    superseded, failed and deleted content is never a candidate.
Nothing is interpolated into SQL except constants and the validated index spec (fixed identifiers);
user text only ever travels as a bound parameter.
"""

from __future__ import annotations

from collections.abc import Sequence

from rag_service.db.database import Conn
from rag_service.features.indexing.ddl import VectorIndexSpec
from rag_service.features.retrieval.filters import NO_FILTER, CompiledFilter
from rag_service.features.retrieval.fusion import Candidate
from rag_service.features.retrieval.query import vector_literal

_VISIBLE = """
  JOIN rag.documents d
    ON d.tenant_id = c.tenant_id AND d.document_id = c.document_id AND d.status = 'active'
  JOIN rag.document_versions v
    ON v.tenant_id = c.tenant_id AND v.document_id = c.document_id
   AND v.version = c.version AND v.state = 'active'
"""

_COLUMNS = (
    "c.chunk_id, c.document_id, c.version, c.ordinal, c.content, c.section_path, "
    "c.page_start, c.page_end"
)


def _fts_sql(user_filter: str) -> str:
    """``user_filter`` is the compiled, allow-listed fragment (placeholders only); it comes AFTER the
    mandatory tenant, ACL and lifecycle predicates and can only narrow them."""
    return f"""
SELECT {_COLUMNS}, ts_rank_cd(c.fts, q.query) AS score
FROM rag.chunks c
{_VISIBLE}
CROSS JOIN websearch_to_tsquery('english', %s) AS q(query)
WHERE c.tenant_id = rag.app_tenant()
  AND c.acl_groups && rag.app_groups()
  AND c.fts @@ q.query{user_filter}
ORDER BY score DESC, c.chunk_id
LIMIT %s
"""  # noqa: S608 - interpolates only module constants and the compiled filter's placeholders


def _candidate(row: dict[str, object]) -> Candidate:
    return Candidate(
        chunk_id=row["chunk_id"],  # type: ignore[arg-type]
        document_id=row["document_id"],  # type: ignore[arg-type]
        version=int(row["version"]),  # type: ignore[call-overload]
        ordinal=int(row["ordinal"]),  # type: ignore[call-overload]
        content=str(row["content"]),
        section_path=None if row["section_path"] is None else str(row["section_path"]),
        page_start=None if row["page_start"] is None else int(row["page_start"]),  # type: ignore[call-overload]
        page_end=None if row["page_end"] is None else int(row["page_end"]),  # type: ignore[call-overload]
        raw_score=float(row["score"]),  # type: ignore[arg-type]
    )


def fts_candidates(
    conn: Conn, query: str, limit: int, flt: CompiledFilter = NO_FILTER
) -> list[Candidate]:
    """Lexical leg. ``websearch_to_tsquery`` accepts arbitrary user text without raising on syntax."""
    rows = conn.execute(_fts_sql(flt.sql), (query, *flt.params, limit)).fetchall()
    return [_candidate(r) for r in rows]


def vector_candidates(
    conn: Conn,
    spec: VectorIndexSpec,
    query_vector: Sequence[float],
    limit: int,
    *,
    ef_search: int,
    iterative_scan: str,
    flt: CompiledFilter = NO_FILTER,
) -> list[Candidate]:
    """Semantic leg over one embedding space. Returns nearest first (cosine distance, smaller is closer).

    The visibility filters run AFTER the approximate scan (pgvector filters post-scan), so recall under
    filtering is protected by iterative scans (ADR-009) and measured by the recall-under-filter test
    (component 8), not assumed."""
    conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))
    conn.execute("SELECT set_config('hnsw.iterative_scan', %s, true)", (iterative_scan,))
    # A generic plan can send a selective filter to the vector index and starve it (ADR-009 measurement).
    conn.execute("SELECT set_config('plan_cache_mode', 'force_custom_plan', true)")
    distance = spec.distance_expression(alias="e")
    sql = f"""
SELECT {_COLUMNS}, {distance} AS score
FROM rag.chunk_embeddings e
JOIN rag.chunks c ON c.tenant_id = e.tenant_id AND c.chunk_id = e.chunk_id
{_VISIBLE}
WHERE e.tenant_id = rag.app_tenant()
  AND c.acl_groups && rag.app_groups()
  AND {spec.query_predicate(alias="e")}{flt.sql}
ORDER BY score, c.chunk_id
LIMIT %s
"""  # noqa: S608 - only fixed identifiers (validated spec) and the compiled filter's placeholders
    params = (vector_literal(query_vector), spec.space, *flt.params, limit)
    rows = conn.execute(sql, params).fetchall()
    # relaxed_order iterative scans may return slightly out of order: restore the exact order
    ordered = sorted((_candidate(r) for r in rows), key=lambda c: (c.raw_score, str(c.chunk_id)))
    return ordered
