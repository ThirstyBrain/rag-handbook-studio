# ADR-017: Chunk Embedding During Ingestion

## Status

Accepted — 2026-11-09. Implemented and verified against a **stand-in model** (the gateway's fake provider); no real embedding model has been run (OI-050), so model choice, tokenizer and retrieval quality remain open (see Evidence gaps).

## Context

Component 5 must turn chunks into vectors. Constraints inherited from earlier decisions:

- The worker **cannot read chunk content** (ADR-016); only the process that has just produced the chunks holds their text.
- All model calls go through the gateway by route name (ADR-012); vectors from different models are incomparable, so the route guards the embedding space.
- Dimension depends on the model (ADR-002), and the store caps indexable dimensions (SRC-131).
- Embedding is a network call to a possibly external provider; it can be slow, fail, or cost money.

## Requirements

No cross-tenant or cross-ACL reads of vectors; no version that has chunks but silently lacks vectors; retries must not duplicate or half-write; model identity, space, recipe and dimension recorded per vector so a model migration is possible; the worker gains no new read rights; no new package.

## Options Considered

- **A. Separate `embed_version` job that reads chunks back.** Clean stage separation and cheap retry of only the embedding step. Rejected: needs a content-reading role for the worker, undoing ADR-016/015.
- **B. Embed inside the ingest job, before the write transaction (selected).** The text is already in memory; chunks and vectors are written in **one** transaction, so a version is never half-embedded. Cost: a provider outage retries extraction and chunking as well (cheap, deterministic, bounded by the sandbox limits).
- **C. Embed in the API process at query time only.** Not an option for documents; kept only for the query side (component 7).
- **D. A dedicated indexer role with read access to staged chunks.** The right answer if embedding must be decoupled from ingestion (large corpora, re-embedding). Deferred: see Reversal Conditions. Re-embedding an existing version in the meantime is done by replaying its ingest job from the retained raw object.

## Decision

1. **Where.** `IngestPipeline` embeds the chunks in memory (`ChunkEmbedder`, batches of `embedding_batch_size`, default 32) and `ChunkStore.replace_chunks` then writes chunks **and** embeddings in the same tenant-scoped transaction. The network call happens outside any transaction.
2. **Sync/async bridge.** The worker is synchronous and the gateway asynchronous with loop-bound HTTP clients, so a small `AsyncBridge` runs one long-lived event loop on a thread (`asyncio.run` per job would break the second job). Each call has a timeout and is cancelled on expiry.
3. **Embedding input recipe `section-path-prefix-v1`.** The text embedded for a chunk is its section path, a blank line, then its content (ADR-003: context the chunk lacks). The recipe name is stored on every vector; changing it means re-embedding.
4. **Storage (migration 0004).** `rag.chunk_embeddings(tenant_id, chunk_id, embedding_space, model, recipe, dimensions, embedding vector)`, primary key `(tenant_id, chunk_id, embedding_space)`, foreign key to chunks with `ON DELETE CASCADE`, `CHECK (vector_dims(embedding) = dimensions)`, forced row-level security. The column is an unconstrained `vector` because dimension depends on the model; component 6 adds approximate indexes per space (expression index cast to the space's dimension, partial on `embedding_space`), the workaround documented by pgvector (SRC-131). `dimensions` is capped at 4000 (the `halfvec` index limit); a plain `vector` index only reaches 2000 (SRC-131).
5. **Access.** `rag_worker`: `INSERT` only, only for chunks it can already see (staged versions of the job's tenant, via the existing chunk policy), plus `SELECT (chunk_id)` on chunks so the policy can resolve; it cannot read, update or delete vectors (replacement happens through the foreign-key cascade when chunks are replaced). `rag_app`: `SELECT` only, and only for vectors whose chunk it may see (tenant **and** chunk ACL through the `EXISTS`). A test pins exactly one policy per role and command.
6. **Derived chunk ids.** `chunk_id = uuid5(namespace, tenant:document:version:ordinal:sha256(content)[:32])` (ADR-003 item 5). The worker cannot read ids back, so it generates them; re-processing identical content yields identical ids (resolves OI-053h for unchanged content).
7. **Validation of provider output** (untrusted data): count equals inputs, every vector has the declared dimension within the configured maximum, every value is finite, no zero vector, a non-empty embedding space that does not change within a version.
8. **Failure policy.** Input the provider will always refuse (`InvalidRequest`, `ContentRefused`) marks the version `failed` with `embedding_rejected` and ends the job permanently. Everything else (outage, rate limit, budget, policy, invalid output, timeout) propagates and the job is retried with backoff; nothing is written until embedding succeeds.
9. **Configuration, not constants.** Route name, batch size, maximum dimensions, data sensitivity and call timeout are settings. The worker **refuses to start** with embedding enabled and no gateway configuration; `RAG_EMBEDDING_ENABLED=false` is an explicit, logged opt-out. The base compose stack sets it to false; `docker-compose.llm.yml` turns it on.
10. **Prerequisite.** pgvector is not a trusted extension, so an administrator installs it (init script / `CREATE EXTENSION` as admin); the migration fails with a clear message if it is missing.

## Rationale

Option B keeps the worker's boundary intact and the version atomic with no new privilege beyond inserting vectors for chunks it just wrote. The retry cost of re-parsing is small next to the embedding call and is bounded. Recording space, model, recipe and dimension per vector is what makes ADR-002's shadow-index migration possible.

## Trade-offs

- A provider outage re-runs extraction on each retry; large documents with a flaky provider waste CPU.
- Embedding inside the ingest job couples ingestion latency to the provider; a slow provider holds a worker for the call timeout.
- No decoupled re-embedding yet: changing the model means replaying ingest for every version (raw objects are retained) while the worker may only write staged versions, so re-embedding an **active** version needs a new path (component 6).
- Unconstrained `vector` loses the type-level dimension guarantee; the `CHECK` and the per-space index restore it.
- Embedding rows duplicate nothing sensitive in the worker's reach but a vector is derived content: it can leak information about the text (embedding inversion is a published research topic; not researched here, no claim made).

## Consequences

Retrieval (component 7) filters by `embedding_space` and joins chunks for ACL; the activation stage (component 6) must require a complete embedding set before activating a version. Operators must supply an embedding route with a model they have verified. Query-time embedding must use the same space and an input recipe matching the document side.

## Security Considerations

Hosted embedding sends chunk text to the route's providers; the route's `sensitivity` (default `internal`) lets the gateway keep `restricted` data on local providers, and per-document sensitivity is not modelled yet. Vectors inherit tenant isolation and chunk ACL through row security. Embedded text may contain hostile instructions; embeddings carry no instructions, but the text itself stays untrusted at generation time. The worker's new privileges are insert-only on one table and `SELECT (chunk_id)`.

## Performance and Cost

Not measured. Cost is the provider's input-token price times total chunk tokens (plus section-path overhead); the pipeline logs tokens, calls, space and fallback use per version so a measured model can be built. No price figures are given because none were researched.

## Reversal Conditions

Move to a decoupled indexer role (option D) when: re-embedding a corpus is needed routinely, ingestion latency is dominated by the provider, or retries of long extractions become costly. Reconsider the unconstrained column if a single model is fixed for the whole deployment.

## Evidence gaps

- No real embedding model has been called (OI-050); the tokenizer is still the character estimate; chunk size versus the model's context is unverified.
- The fake provider produces hash-derived vectors, which proves the plumbing, not retrieval quality.
- pgvector limits were read from the README via a fetch summary (SRC-131).

## References

SRC-009, SRC-015, SRC-016 (ADR-002), SRC-131 (pgvector README). ADR-002, ADR-003, ADR-012, ADR-013, ADR-015, ADR-016.
