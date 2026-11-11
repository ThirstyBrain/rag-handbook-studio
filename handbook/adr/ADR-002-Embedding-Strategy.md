# ADR-002: Embedding Strategy

## Status

Proposed — 2026-11-07. Partially evidence-backed; final model choice deferred to the Ch. 5 research batch and the M5 retrieval benchmark.

## Context

Embeddings define retrieval quality and are expensive to change: switching models requires re-embedding the corpus [SRC-009]. The store (ADR-001) caps indexable dimensions.

## Requirements

Local, no-cost default; a cloud option; multilingual not required for the reference corpus (assumption); model identity and dimension recorded per vector so a migration is possible without downtime.

## Options Considered

- A: Local model via Ollama, e.g. `embeddinggemma` (300M parameters, 2K context, 622 MB on disk [SRC-016]); dimensions and license not confirmed on the page.
- B: Azure OpenAI `text-embedding-3-small` (1,536 dims) or `-3-large` (3,072 dims), 8,192 input tokens [SRC-009].
- C: Cohere embed v4/v5 offered via Azure Foundry (multiple output dims) [SRC-009] — not otherwise researched.

## Decision

Define an `Embedder` port with `model_id`, `dimensions`, and `embed(batch)`; store `(embedding, model_id, dimensions)` per chunk; default adapter A; second adapter B using `text-embedding-3-small` (fits a plain `vector` index) with `-3-large` documented as requiring `halfvec` or reduced dimensions. Ollama vectors are L2-normalized [SRC-015], so cosine and inner product are equivalent for them — verify per model before relying on it.

## Rationale

Local-first respects cost preference and keeps CI reproducible. Per-vector model metadata makes a dual-write / shadow-index migration feasible.

## Trade-offs

Small local models generally trail large hosted ones on quality — **unverified here; to be measured** on the golden dataset. The 2K context of the local model constrains chunk size (ADR-003).

## Consequences

Re-embedding pipeline and index versioning are first-class features. Evaluation must run for every embedding change (CLAUDE.md §12).

## Security Considerations

Hosted embedding sends chunk text to a provider; data-handling terms must be reviewed per deployment (research pending). Local option avoids this.

## Performance and Cost

Embedding cost is per token at ingest (one-time per chunk) plus per query. No pricing was researched; no figures given.

## Reversal Conditions

Benchmark shows local model recall materially below hosted option on the golden set; dimension/storage constraints change; model retirement.

## References

SRC-009, SRC-015, SRC-016.
