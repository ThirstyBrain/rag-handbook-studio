# ADR-004: Retrieval Architecture (Hybrid, Permission-Aware)

## Status

Proposed — 2026-11-07. Design grounded in SRC-001, 004–008; must be validated by the M5 benchmark.

## Context

Enterprise queries mix semantic questions and exact identifiers (error codes, policy IDs, names). Every query must be constrained by tenant and document ACL **during retrieval**, not after generation.

## Requirements

Hybrid lexical + vector retrieval; fusion without score calibration; hard tenant boundary; document-level ACL; stable recall under selective filters; reranking hook; bounded candidate counts.

## Options Considered

- A: Vector-only. Misses exact identifiers; Azure guidance notes codes, jargon, dates and names favor keyword search [SRC-005].
- B: Hybrid with Reciprocal Rank Fusion: score = Σ 1/(rank + k), commonly k=60, merging ranked lists without comparing raw scores [SRC-006]; pgvector also points to RRF or cross-encoder for hybrid [SRC-001].
- C: Hybrid with weighted score normalization. Not researched.

## Decision

Option B: two parallel candidate queries (FTS and vector), each limited to N candidates and each filtered by tenant + ACL inside the query; fuse with RRF in application code (a small, testable function); optional rerank stage; context assembly after.

Filtering design:
1. **Tenant**: Postgres RLS as the hard boundary; application role without BYPASSRLS [SRC-004]. Plus an explicit `tenant_id` predicate for index/plan friendliness (defense in depth, not a replacement).
2. **ACL**: principal list stored per document/chunk, matched with array overlap — analogous to the security-trimming pattern in Azure AI Search where the principal is only a string and enforcement relies on applying the filter to every query [SRC-008].
3. **Recall under filters**: because pgvector filters after the ANN scan [SRC-001], enable iterative scans, set `hnsw.max_scan_tuples` consciously, and use partial indexes or partitioning for high-volume tenants (documented pgvector guidance [SRC-001]). Add a recall-under-filter test to the benchmark. Azure AI Search `preFilter` is the managed equivalent [SRC-007].

## Rationale

RRF avoids calibrating incomparable score scales (BM25-style vs. similarity). Enforcing filters in-query ensures unauthorized chunks never reach the prompt.

## Trade-offs

RRF discards score magnitude; two queries per request add latency; ACL arrays can be large and low-selectivity-hostile for ANN. Postgres FTS ranking is not documented as BM25 [SRC-003] — lexical quality must be measured.

## Consequences

Retrieval service owns candidate limits, fusion, and filter construction; the LLM prompt is never the authorization boundary. Tests: cross-tenant, ACL, selective-filter recall.

## Security Considerations

RLS caveats: RI checks bypass RLS (covert channel); policies with subqueries can race under READ COMMITTED; superuser/owner roles bypass unless FORCE is set [SRC-004]. Do not rely on `retrievable=false`-style hiding as security [SRC-008].

## Performance and Cost

Azure's own benchmark reports prefiltering slower than postfiltering, up to ~7x at high selectivity, **vendor-reported on their service** and not transferable to pgvector [SRC-007]. Our figures must be measured.

## Amendment 2026-11-07 (Chapter 9 research)

- **Fusion evidence:** the original RRF paper was read in full: `1/(k + rank)`, k = 60 fixed in a pilot and near-optimal but not critical; RRF beat the best single system and Condorcet/CombMNZ by 4–5% on average in its experiments (fusing many diverse systems) [SRC-067]. Default stays unweighted RRF with k = 60, to be swept on the golden set; weights default to 1.0.
- **Lexical leg:** start with `ts_rank_cd` and a language-appropriate text-search configuration. Documented difference: Postgres built-in ranking uses no global (collection) statistics [SRC-003] whereas BM25's IDF does [SRC-065]. The *quality* gap is unmeasured (OI-030). Candidate alternative: pg_search BM25 (AGPL-3.0/commercial; PG ≥ 14; not on Windows) [SRC-066] — licence review required.
- **Analyzers first:** an executed toy example showed a morphology miss (no stemming) ranking a less relevant document above the relevant one; analyzer work precedes fusion tuning (Ch. 9).
- **Filters inside both legs** (Ch. 8 §8.4.11); shared collection statistics in a shared index are not tenant-scoped [SRC-076]; do not expose raw scores.
- **Reversal triggers added:** normalised score fusion beats RRF by a margin that survives outlier tests; `ts_rank_cd` trails BM25 materially on identifier/jargon queries; engine-native hybrid (Azure AI Search) becomes the platform.

## Reversal Conditions

Recall-under-filter target missed; RRF underperforms a tuned weighted fusion on the golden set; ACL cardinality makes array-overlap filtering too slow (move to a permission-index/join or Azure AI Search).

## References

SRC-001, 003, 004, 005, 006, 007, 008.
