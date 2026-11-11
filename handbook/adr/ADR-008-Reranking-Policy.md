# ADR-008: Re-Ranking Policy

## Status

Proposed — 2026-11-08. Evidence from Chapter 12 research (SRC-064, 094–101, mostly abstract- and documentation-level) and an executed mechanics demo that uses a hand-written stand-in scorer (no neural reranker run; OI-043). Must be validated with a real reranker on the M5 golden dataset before acceptance.

## Context

First-stage retrieval compares precomputed representations and misorders some candidates. A second-stage reranker scores query–document pairs jointly and can improve ordering of a short list, at the cost of latency, money, a new failure mode, and — if external — a data-egress path. Evidence reviewed: two-stage retrieve-and-rerank is the documented pattern [SRC-098]; BEIR reports re-ranking and late interaction best on average zero-shot at high computational cost [SRC-064]; a managed ranker reranks only the top 50 and cannot recover documents outside them [SRC-100]; score scales differ across rerankers and drift with updates [SRC-100, SRC-101].

## Requirements

Measurable lift over the hybrid baseline per query class; bounded latency (hard timeout); graceful degradation to first-stage order; no restricted text ever reaches the reranker; auditable configuration (model, version, N); testability without the model.

## Options Considered

- **A: No reranker** (hybrid retrieval only).
- **B: Managed semantic ranker** (Azure AI Search) [SRC-100].
- **C: Managed reranking API** (for example Cohere Rerank) [SRC-099].
- **D: Self-hosted open-weights cross-encoder** (for example bge-reranker-v2-m3) [SRC-101].
- **E: Late-interaction model** [SRC-095].
- **F: LLM listwise reranking** [SRC-097].

## Decision (proposed)

1. **Hybrid retrieval is the baseline;** add a reranker only where error analysis shows ordering errors *within* the candidate set (candidate recall@N high, post-retrieval ordering poor).
2. Put the reranker behind a `Reranker` port with a **timeout, circuit breaker and first-stage-order fallback**; emit a fallback metric.
3. **Authorize first:** tenant/ACL filters are applied inside retrieval, the cut to N happens after them, and only authorized text is sent to any reranker (executed in the Ch. 12 demo, with a mutant that violates it).
4. Choose **N from the measured candidate recall@N curve** and the latency budget; record N in the index/config version.
5. Default implementation: **B** if the platform is Azure AI Search and data classification allows (ADR-001); otherwise **D** behind the port; **C** only after a data-processing review; **E/F** are evaluated experiments, not defaults.
6. **Score policy:** never copy thresholds across models or versions; abstention thresholds are calibrated on labelled answerable and unanswerable queries and re-calibrated on every model change.
7. **Windowing:** rerank inputs are sized to the model's limit; long inputs are windowed with max aggregation, or chunks are sized to fit.
8. Prompt ordering (edge ordering) and passage count are **A/B-tested**, not assumed.
9. Every reranker change triggers the golden-set regression (CLAUDE.md §12).

## Rationale

The pattern is widely documented and cost-bounded by N; the ceiling and authorization properties were verified mechanically; managed and open options cover different data-handling postures; the decision defers adoption to evidence because the lift is unmeasured here.

## Trade-offs

A reranker adds latency (≈ linear in N), cost and an operational dependency; a conservative gate may leave quality unclaimed until measured; self-hosting shifts cost to operations; managed services shift risk to data egress and vendor model changes.

## Consequences

`Reranker` port, rerank adapter implementations, candidate-recall@N and post-rerank nDCG@k in the evaluation harness, per-stage latency and fallback metrics, calibration datasets with unanswerable queries.

## Security Considerations

Authorization precedes the call; external rerankers are sub-processors (terms unreviewed, OI-043); LLM rerankers read untrusted text (constrained output schema, no tools); cache keys include tenant and permission digest; no passage text in logs.

## Performance and Cost

Latency ≈ N × per-pair time ÷ parallelism (formula executed with an assumed 4 ms placeholder, not a measurement); cost depends on vendor pricing (not collected). Measure both in M5/M6.

## Reversal Conditions

First-stage improvements erase the lift; a vendor model update causes unmanageable drift; the egress review fails; cost per answer exceeds value; an LLM or late-interaction option beats the cross-encoder at acceptable cost on the golden set.

## Evidence gaps

No real reranker was run; ColBERT and RankGPT read at abstract level; no vendor prices or terms; Cohere page undated; latency and quality unmeasured (OI-043).

## References

SRC-062, 064, 067, 094–101 (see RESEARCH-REGISTER).
