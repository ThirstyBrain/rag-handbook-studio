# ADR-001: Reference Implementation Technology Selection

## Status

Accepted (conditional) — 2026-11-07. Revised from the M0 proposal after M1 research. Conditions are listed under Reversal Conditions and are tested by the M5 benchmark corpus.

## Context

The handbook needs one coherent, runnable reference implementation (`reference-implementation/`) for experienced Azure/.NET architects. Owner preferences: cost-first, local AI before cloud AI, minimal packages, clean/feature-first architecture, ADR-driven. Dev host (verified 2026-11-07): Windows 11, Python 3.14.2, Node 24.13.1, Docker 29.0.1, Ollama installed (not running), NVIDIA GTX 1650 GPU, no local Postgres, no Azure CLI.

## Requirements

Functional: the 23 capabilities in the Master Prompt. Non-functional: tenant isolation enforced in the data layer; permission-aware retrieval; observability; runs locally with no paid service; deployable to Azure; testable in CI.

## Options Considered

**Retrieval store**
- A: PostgreSQL + pgvector + built-in full-text search. One datastore, transactional, row-level security available [SRC-001, SRC-003, SRC-004].
- B: Azure AI Search. Managed hybrid (BM25 + vector, RRF), semantic ranker, filter modes, security-trimming pattern [SRC-005–008]. Cloud-only for development; cost not yet researched.
- C: Dedicated vector DB (Qdrant, Weaviate, Milvus, Pinecone) + relational DB. **Not researched in M1**; excluded from the decision, not rejected on evidence. Revisit in the Ch. 5 research batch.

**Backend**: Python/FastAPI vs. .NET. **Frontend**: Next.js/TypeScript. **LLM/embeddings**: provider abstraction (local runtime + Azure OpenAI). **Observability**: OpenTelemetry. **Deployment**: Azure Container Apps vs. AKS vs. App Service (only Container Apps managed-identity docs reviewed [SRC-018]).

## Decision

1. **Postgres + pgvector + Postgres FTS** as the default store, behind a `Retriever` / `VectorStore` port so Azure AI Search can be a second adapter (documented, optionally implemented).
2. **Python + FastAPI** backend (FastAPI 0.162.1 requires Python ≥3.10, Pydantic ≥2.9 [SRC-013]). Target Python 3.12 or 3.13 in Docker for library compatibility; the dev host's 3.14.2 is not assumed compatible with all dependencies — verify in M5.
3. **Next.js + strict TypeScript** frontend.
4. **Provider abstraction**; local-first default (Ollama, `/api/embed` returns L2-normalized vectors [SRC-015]) and Azure OpenAI as the second provider. See ADR-002.
5. **OpenTelemetry** for traces/metrics. GenAI semantic conventions have moved to a separate repo with no confirmed stability status [SRC-011, SRC-012] — treat attribute names as unstable; wrap them in one module.
6. **Docker Compose** for dev; **Azure Container Apps with managed identity** as the documented deployment target [SRC-018].

## Rationale

One store gives transactional ingestion/deletion, tenant isolation via RLS, and zero-cost local runs. RLS is default-deny once enabled, supports USING/WITH CHECK, and is the correct place for a hard tenant boundary [SRC-004]. FastAPI/Python gives the strongest ecosystem for document processing and evaluation.

## Trade-offs

- **Filtered ANN recall.** pgvector applies filters *after* the approximate index scan, so selective filters can return fewer than K rows; iterative scans (0.8.0+) mitigate this [SRC-001]. Azure AI Search's `preFilter` mode guarantees K results if they exist, at higher cost [SRC-007]. This matters directly for permission-aware retrieval; ADR-004 addresses it.
- **Lexical quality.** The Postgres docs reviewed describe `ts_rank`/`ts_rank_cd` with no global statistics and do not mention BM25 [SRC-003]; Azure AI Search uses BM25 [SRC-005]. Expect weaker lexical ranking on Postgres; this is a hypothesis to be measured, not a verified conclusion.
- **Dimension ceiling.** pgvector indexes `vector` up to 2,000 dims and `halfvec` up to 4,000 [SRC-001]. `text-embedding-3-large` outputs 3,072 dims [SRC-009] — it needs `halfvec` or reduced dimensions to be indexed.
- Python adds a second language for a .NET-centric reader; accepted and discussed in the chapters.

## Consequences

Chapters present Azure AI Search, dedicated vector DBs, and .NET/Semantic Kernel as first-class alternatives with selection criteria. The benchmark corpus must include selective-filter and exact-identifier queries.

## Security Considerations

RLS enforces tenant boundary; the application connects as a non-owner, non-superuser, non-BYPASSRLS role (these bypass RLS [SRC-004]). Referential-integrity checks bypass RLS and can be covert channels; schema design must account for it. Managed identity on Azure; no secrets in repo.

## Performance and Cost

No measurements exist. All figures come from reproducible benchmarks in M5/M6, labelled by type. Vendor-run benchmarks are cited only as vendor-reported.

## Amendment 2026-11-07 (Chapter 5 research)

Option C (dedicated vector databases: Qdrant, Weaviate, Milvus, Pinecone) plus Elasticsearch, Redis and FAISS were reviewed at documentation level (SRC-039–052). **No benchmark was run, so the decision is unchanged.** Findings that sharpen the trade-offs: pgvector filters after the ANN scan (10% selectivity ≈ 4 of 40 candidates at default `ef_search`), with iterative scans, partial indexes and partitioning as documented mitigations [SRC-001]; Qdrant documents payload-partitioned multitenancy as its default, with sharding and tiered options [SRC-042]; Weaviate documents shard-per-tenant [SRC-045] (scale claims are vendor-reported); Azure AI Search offers prefilter semantics [SRC-007]. Tenancy pattern in the reference implementation: shared index for small tenants (exact search on the filtered subset), partitions or dedicated indexes for large tenants, RLS as the boundary (ADR-004). OpenSearch was not researched (docs did not load).

## Verification 2026-11-07 (executed, not documentation)

`python -I scripts/verify-sql.py` runs five SQL files against PostgreSQL 16.12 + pgvector 0.8.7 (built from source; the `pgvector/pgvector:0.8.7-pg17` image pull failed on a CDN error): documented defaults, operator semantics, storage sizes, dimension limits (vector ≤ 2,000, halfvec ≤ 4,000 for HNSW), operator-class matching, measured HNSW/IVFFlat recall curves, filtered-search starvation and its iterative-scan remedy, RLS behaviour, text-search tokenisation/stemming, the hybrid RRF function, and the document schema. Findings that matter to this decision: filtered ANN starvation is **real and measured** (4.00 of 10 at a 10% filter; 2.03 of 10 under RLS at ~5%), iterative scans fix it on synthetic data, and `ts_rank`/`ts_rank_cd` score a rare and a common term identically. All numbers are on small synthetic datasets and PostgreSQL 16 (OI-036, OI-037); the reversal conditions below remain to be tested on a real corpus in M5.

## Reversal Conditions

Reconsider if: pgvector with iterative scans cannot reach the recall target on selective tenant/ACL filters in the M5 benchmark; Postgres FTS lexical quality is materially worse than a BM25 baseline on the identifier-heavy queries; a dependency does not support the chosen Python version; the user prefers .NET; Azure AI Search becomes the mandated production standard.

## References

SRC-001, 003, 004, 005, 007, 009, 011, 012, 013, 015, 018 (see RESEARCH-REGISTER).
