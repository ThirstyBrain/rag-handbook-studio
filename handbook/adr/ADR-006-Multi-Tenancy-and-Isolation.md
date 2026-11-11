# ADR-006: Multi-Tenancy, Authorization and Isolation

## Status

Proposed — 2026-11-07. Evidence from Chapter 8 research (SRC-004, 072–077); several elements depend on unexecuted SQL (OI-027) and unresearched topics (per-tenant keys, model-endpoint residency).

## Context

The reference implementation serves many tenants and many users per tenant. A cross-tenant or cross-permission disclosure is the highest-severity failure mode (Ch. 8). ADR-001 chose Postgres + pgvector; ADR-004 chose in-query filtering; this ADR fixes the tenancy and permission model.

## Requirements

Hard tenant boundary independent of application bugs; document-level permissions with immediate revocation; filters inside every retrieval leg before limits; auditability including denials; residency by routing; defined RPO/RTO; deletion propagation; testable policy.

## Options Considered

- **Topology:** (A) shared tables + `tenant_id` + RLS; (B) tiered (shared for small tenants, dedicated partitions/indexes for large); (C) database/stack per tenant; (D) Azure AI Search patterns (index per tenant, service per tenant, hybrid, shared index) [SRC-076].
- **Permissions:** (A) group-id ACLs resolved at query time + ABAC attributes compiled to filters; (B) user-expanded ACLs at ingest; (C) native Azure AI Search token-based trimming (preview) [SRC-072].
- **Keys:** platform-managed vs. per-tenant customer-managed (unresearched for Postgres).

## Decision (proposed)

1. **Topology B**: shared Postgres tables with `tenant_id`, `acl_groups`, `classification`, `region` denormalised onto every chunk row; RLS enabled with `FORCE ROW LEVEL SECURITY`; application connects as a non-owner, non-superuser, non-BYPASSRLS role [SRC-004]; large tenants get dedicated partitions/indexes; small tenants use exact search on the filtered subset (ADR-004, Ch. 5).
2. **Permissions A**: ACLs store **group ids**; the caller's groups come from the validated token at query time; ABAC rules are compiled into filters over stored attributes; a **policy↔filter equivalence property test** and mutation checks gate CI (executed model in Ch. 8). Missing ACL metadata fails closed.
3. **Identity**: tenant derived from token; immutable identity object passed through the pipeline; **database identity set per transaction only (`SET LOCAL` / `set_config(..., true)`), never at session scope** (measured leak, above); a missing identity must error, not return empty results, and such errors are alerting signals; OBO only where a downstream service needs the user [SRC-073]; never relay middle-tier tokens.
4. **Audit**: application-level, append-only, includes denials, no raw content (platform logs do not capture user identities [SRC-075]).
5. **Residency**: tenant → region → stack routing; no cross-region fallback that violates the tenant constraint.
6. **DR**: zone-redundant HA for Postgres; raw documents geo-redundant; index rebuilt from raw documents; ACLs rebuilt from the identity source; documented RPO/RTO per data class; restore + cross-tenant test drills [SRC-077, SRC-054].
7. **Keys**: platform-managed encryption by default; per-tenant keys deferred pending research.

## Verification (2026-11-07, PostgreSQL 16.12 + pgvector 0.8.7; `scripts/verify-sql/03-rls.sql`)

Executed, synthetic 20,000-row table, application role that is not owner/superuser/BYPASSRLS: superuser and table owner bypass RLS until `FORCE ROW LEVEL SECURITY`; the policy returned exactly the rows a direct predicate predicts (673 = 673); cross-tenant INSERT is rejected (`WITH CHECK` defaults to `USING`); `row_security = off` errors instead of bypassing; a **transaction-scoped** identity (`SET LOCAL`) disappears at commit and the next query **fails closed with an error**; a **session-scoped** identity **leaked** into a request that never set one (it saw 2,962 rows of another tenant); and with an HNSW index a tenant holding ~5% of rows received **2.03 of 10** results by default (10.00 with `hnsw.iterative_scan = relaxed_order`), with the policy predicates shown as a `Filter:` on the index scan. These measurements change the decision text: identity **must** be transaction-scoped, and RLS **does not** remove the need for the filter-starvation mitigations.

## Rationale

RLS provides a default-deny backstop independent of application code [SRC-004]; group ACLs revoke immediately whereas user-expanded ACLs persist until sync (executed model; Azure also prefers groups [SRC-072]); compile-and-test prevents policy/filter drift; tiered topology matches skewed tenant sizes (Ch. 5).

## Trade-offs

RLS adds policy complexity and requires role discipline; RI checks bypass RLS and sub-select policies race under READ COMMITTED [SRC-004], so policies must be current-row predicates. Group-id ACLs require query-time group resolution (latency, bounded caching). Tiered topology adds placement and migration logic (tenant-placement catalog [SRC-076]).

## Consequences

Chunk schema carries permission fields; ingestion captures ACLs (Ch. 3); caches key on tenant + permission set + index version (Ch. 7); evaluation includes cross-tenant and revocation tests; shared-statistics effects on lexical ranking are monitored per tenant (Ch. 9 [SRC-076]).

## Security Considerations

See Ch. 8 §8.4.2 (isolation layers) and Ch. 22. Preview Azure features are not used in the default path (no SLA [SRC-072]).

## Performance and Cost

Current-row RLS predicates are the fastest form [SRC-004]; ingest-time denormalisation avoids per-query joins. No measurements yet. HA standby doubles database compute cost [SRC-077].

## Reversal Conditions

Contract or regulation requires physical per-tenant isolation or per-tenant keys; RLS overhead or planner behaviour breaks latency targets with partitioned vector indexes; Azure AI Search native token-based trimming reaches GA and becomes the platform; group resolution latency or revocation window cannot meet requirements.

## Evidence gaps

Per-tenant key support in Azure Postgres/Search (OI-032); model/embedding endpoint residency (OI-033); RLS behaviour under real pooler software (PgBouncer transaction pooling), at realistic scale and with partitioned tables, and on PostgreSQL 17/18 (OI-036, OI-037); official DPDP text and GDPR transfer provisions (OI-028, OI-029). Resolved by execution: RLS semantics, identity scoping, RLS + HNSW filtering behaviour (OI-027).

## References

SRC-004, 054, 072–079 (see RESEARCH-REGISTER).

## Implementation note 2026-11-09 (component 2, ADR-013)

The shared-schema tier is implemented: `rag_app` (no BYPASSRLS, DML only), forced RLS, per-command policies, composite tenant keys, transaction-local identity with fail-closed functions, and a pooled access layer. Verified on PostgreSQL 16.12 with 26 isolation tests and mutation testing (15/15). Not implemented: per-tenant partitions/indexes (ADR-009 option D), tenant provisioning (OI-051), RLS performance measurement.
