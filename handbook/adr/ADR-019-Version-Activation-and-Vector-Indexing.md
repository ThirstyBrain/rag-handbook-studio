# ADR-019: Version Activation and Vector Indexing

## Status

Proposed — 2026-11-10. **Authored without a database**: migration 0005, `ChunkStore.activate_version`, the pipeline change and the updated integration tests have NOT been executed (Docker and PostgreSQL were unavailable; the user allowed unverified authoring). Only the pure index-DDL module is unit-tested (272 unit tests pass). Promote to Accepted after the integration suite and `scripts/verify-sql.py` pass.

## Context

No code moved a version from `staged` to `active`, so no chunk could ever be retrieved. Vectors are stored in an unconstrained `vector` column (ADR-017), which pgvector cannot index directly. Retrieval (component 7) needs (a) a rule for when a version becomes visible and (b) an approximate index per embedding space.

## Requirements

A version is visible only when complete; at most one active version per document; replacing a version is atomic; the worker gains no read right on content or vectors; index creation does not block writes; no new package.

## Options Considered

- **A. Activate in the same transaction as the chunk write.** Atomic, but the existing tests and failure semantics (a staged version that has chunks) change, and a retry after a failed activation would still be correct. Rejected for now: separating the steps keeps "complete staged version" a visible, testable state.
- **B. Activate in a second transaction at the end of the ingest job (selected).** Chunks and vectors are written atomically first; activation is a short second transaction.
- **C. A separate indexer role and job.** Cleanest separation and the path for re-embedding active versions; needs a new role and a content-free completeness check. Deferred (ADR-017 option D).
- **Index: one global index vs. per-space expression indexes.** A global index cannot exist with mixed dimensions; per-space partial expression indexes (selected) are the pgvector-documented workaround.

## Decision

1. **Activation** is `ChunkStore.activate_version`: in one transaction, older active versions become `superseded`, then the staged version becomes `active`. If the version is not staged the transaction rolls back and the result is `stale`; a unique violation (a newer version is already active) also yields `stale`.
2. **Database guards (migration 0005):** a partial unique index allows one `active` version per document; `rag_worker` may move `staged → active` only if the version has at least one chunk, and `active → superseded`; nothing else about active versions.
3. **Completeness of vectors** ("every chunk has an embedding") is enforced by the application, which wrote chunks and vectors in one transaction. A policy cannot check it without giving the worker `SELECT` on `chunk_embeddings`, which ADR-017 withholds. Residual risk: a bug in app code could activate a version with missing vectors; the database would not catch it. A later indexer role (option C) can close this.
4. **Vector index:** `VectorIndexSpec` generates `CREATE INDEX CONCURRENTLY` for `hnsw` over `embedding::vector(D)` (or `halfvec(D)` above 2000 dimensions), partial on `embedding_space = '<space>' AND dimensions = D`, with `m = 16` and `ef_construction = 64` as starting values. The same object emits the query's distance expression and predicate so planner and index cannot drift. An operator runs `python -m rag_service.features.indexing.manage` once per space.
5. **Retrieval must restrict itself to active versions** with an explicit predicate (component 7). A restrictive row-level policy on `rag_app` for the same purpose was considered and not added, because it would change every existing test that reads staged chunks; it remains a hardening option.
6. **Full-text index:** `rag.chunks.fts` and its GIN index already exist from migration 0001; no change.

## Rationale

Activation as the last, small step keeps the failure and retry story simple and makes completeness a database-visible state. Per-space partial expression indexes are the only way to index mixed-dimension spaces with one table.

## Trade-offs

- Two transactions: a failure between them leaves a complete but invisible staged version; the job retry repeats embedding (cost) before activating.
- Vector completeness is an application guarantee, not a database one (decision 3).
- `halfvec` above 2000 dimensions trades precision for indexability; the effect on recall is unmeasured.
- Partial expression indexes require every query to repeat the exact cast and predicate.
- `ef_construction`/`m` values are starting points, not tuned; no recall or latency was measured for them in this ADR.

## Consequences

Retrieval can rely on `state = 'active'`. Operators must create an index per space before enabling vector search at scale (small corpora work with a sequential scan). Re-embedding an active version still has no path.

## Security Considerations

The worker's new privileges are limited to two UPDATE policies on version state in its own tenant. It still cannot read content or vectors. Activation is the point where content becomes retrievable, so a bug here is a visibility bug; the integration test pins which transitions the worker may make.

## Performance and Cost

Not measured. HNSW build time and memory, and recall at the chosen parameters, must be measured with `evaluation/bench_pgvector.py` before any claim. `CREATE INDEX CONCURRENTLY` avoids blocking writes but is slower and can leave an invalid index if interrupted (handled by the management command).

## Reversal Conditions

Move to a dedicated indexer role when re-embedding active versions or database-enforced vector completeness is required; reconsider HNSW vs. IVFFlat if build memory or time dominates (to be measured).

## Evidence gaps

pgvector limits and operator classes come from the README (SRC-131, read at README level only); the generated DDL has not been executed against PostgreSQL; default `m` and `ef_construction` are the README's documented defaults as I recall them and must be re-checked against the source.

## References

SRC-131 (pgvector README). ADR-009, ADR-013, ADR-015, ADR-016, ADR-017.
