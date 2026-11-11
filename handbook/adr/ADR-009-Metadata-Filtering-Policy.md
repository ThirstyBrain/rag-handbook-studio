# ADR-009: Metadata Filtering and Filter Execution Policy

## Status

Proposed — 2026-11-08. Evidence from Chapter 13 research (SRC-001, 007, 102–105) and executed experiments on PostgreSQL 16.12 + pgvector 0.8.7 with small synthetic data (`scripts/verify-sql/06-metadata-filtering.sql`, `docs/exercises/ch13_filter_compiler.py`). PG16 only; synthetic 16-dimensional vectors; no concurrency or latency measurements (OI-044).

## Context

Retrieval must apply security, validity and relevance constraints. With an ANN index a filter can remove most candidates, returning fewer than k results without error. The measured behaviour depends on filter selectivity and on whether the statement is planned with a custom or generic plan. Filters also arrive from untrusted sources (users, LLM self-query).

## Requirements

Never return another tenant's or an unauthorized document; return k results whenever k matching rows exist; predictable behaviour across selectivity bands; filter compilation that is injection-safe and cannot widen security predicates; observability of silent under-retrieval.

## Options Considered

- **A: Post-filter on one global ANN index** (default pgvector behaviour).
- **B: Global index + iterative scan** (+ forced custom plans).
- **C: Partial indexes** for hot filter values.
- **D: List partitioning with per-partition indexes** (tenant-local).
- **E: Engine with in-algorithm/pre-filtering** (for example Azure AI Search `preFilter`) [SRC-007] or ACORN-style indexes [SRC-102].

## Decision (proposed)

1. **Typed metadata columns** for hot filters; JSONB only for the long tail, verified with `EXPLAIN` (one key measured only).
2. **One filter compiler** (allow-listed fields/operators, type checks, size/depth limits, bind parameters only). The mandatory predicates (tenant, ACL, not-deleted) are built by the platform from the verified identity and AND-ed outside the user predicate; user or LLM filters cannot name them. Row-level security remains the backstop (ADR-006).
3. **Default execution (B):** global HNSW with `iterative_scan` enabled for filtered queries, `ef_search` tuned from a recall sweep, `plan_cache_mode = force_custom_plan` (or no server-side prepared statements) for the filtered kNN query, `ANALYZE` after bulk loads.
4. **Large, stable tenants (D, then C):** partition-local indexes for tenants above a size threshold; partial indexes for a few hot values. The long tail uses the shared index (ADR-006 tiering).
5. **Monitoring is required:** results returned vs. k, recall against an exact scan on a sample, plan type, filter-selectivity histogram.
6. **LLM-extracted filters** are suggestions or soft boosts by default; hard application requires measured extraction accuracy; the extracted filter (not the question) is logged.
7. Missing-value and array-quantifier policies are defined per attribute and tested.
8. Re-run the SQL verification suite when PostgreSQL, pgvector, schema or index choices change.

## Rationale

Measured: a 10% filter returned 4.10/10 by default and 10.00 with iterative scan; 1% and 0.1% filters were served correctly by a planner-chosen btree plan, but a generic plan sent them to HNSW and returned 0.45 and 0.00 of 10; a partition-local index kept a 10% tenant at 10/10 and pruned the query to one of three partitions; a partial index served only its own predicate. The compiler properties were verified with seven injected defects all detected.

## Trade-offs

Iterative scan adds latency and `relaxed_order` relaxes ordering; forcing custom plans costs planning time; partitions and partial indexes multiply index build/memory/maintenance; strict allow-lists reduce filter flexibility; conservative LLM-filter handling reduces convenience.

## Consequences

Filter compiler module and tests; index strategy by tenant size class; migrations for partitions/partial indexes; metrics and alerts for under-retrieval; data-access-layer test that checks plan type through the real driver.

## Security Considerations

Mandatory predicates cannot be skipped or overridden; values are parameters only; facet counts computed over the authorized set; error messages do not echo other tenants' schema; self-query injection cannot affect isolation (relevance only).

## Performance and Cost

No latency measured. Indexes per partition or value cost storage (vector index ≈ 1.33× raw vector bytes at 1536-d in the Ch. 5 measurement); global iterative scan costs query-time latency. Vendor benchmark (Azure pre- vs. post-filter) is vendor-reported and unreproduced.

## Reversal Conditions

Starvation persists despite iterative scan; partition count or memory becomes unmanageable; extraction accuracy is too low for hard filters; PostgreSQL/pgvector changes the planner or filter behaviour; a managed engine with robust in-algorithm filtering replaces PostgreSQL (ADR-001).

## Evidence gaps

PG16 only (docs describe PG18); synthetic low-dimension data; no concurrency, latency, pooler or driver tests; `plan_cache_mode = auto` flipping not measured; JSONB tested with one key; Qdrant filterable-HNSW section and ACORN full paper unread (OI-044, OI-045).

## References

SRC-001, 007, 057, 102–105 (see RESEARCH-REGISTER).
