# ADR-013: Database Schema, Roles, Migrations and Tenant-Scoped Access

## Status

Accepted — 2026-11-09 (implemented and verified on PostgreSQL 16.12 with synthetic test data; PG16 only, OI-036). Supersedes ADR-011 item 8 (database access pattern). Implements ADR-006 (multi-tenancy and isolation) for the shared-schema tier.

## Context

The service needs a tenant-isolated relational store that later components (ingestion, indexing, retrieval) build on. ADR-001 and ADR-006 require the application to connect as a non-owner, non-superuser, non-BYPASSRLS role and to enforce isolation in the data layer. Earlier chapters measured the hazards: a session-level identity setting leaks across pooled requests, a missing identity must fail closed, RLS on an ANN index starves selective tenants (Chapters 8, 13). ADR-011 left the sync-versus-async driver choice open because psycopg's async API cannot run on Windows' default event loop.

## Requirements

Isolation enforced by the database, not by application code or prompts; identity can never survive into another request; tenant, ACL and lifecycle integrity enforced by constraints; forward-only, reviewable, repeatable schema changes that cannot be silently edited; least-privilege roles; works on the Windows dev host and Linux containers; no unnecessary dependencies.

## Options Considered

- **Migrations:** A) Alembic (brings SQLAlchemy), B) a plain-SQL runner of our own (chosen), C) a standalone migration tool in a container (not researched).
- **Access pattern:** A) async psycopg (needs a selector event loop on Windows), B) synchronous psycopg and `psycopg_pool` in worker threads (chosen).
- **Isolation:** A) application-side filters only, B) RLS only, C) RLS plus constraints plus least-privilege roles (chosen).
- **Roles:** A) one login role, B) separate owner and application roles (chosen).

## Decision

1. **Roles.** `rag_owner` owns all objects and runs migrations; `rag_app` is what the API connects as. Neither is superuser, `CREATEDB`, `CREATEROLE` or `BYPASSRLS`. A bootstrap script (`database/init/10-roles.sh`) creates them from environment-supplied passwords on first initialisation. The bootstrap superuser is used only for that and for scratch databases in tests.
2. **Schema `rag`** with `tenants`, `documents`, `document_versions`, `chunks` and `schema_migrations`. Every tenant-owned table carries `tenant_id` in its primary key; composite foreign keys include it, so a cross-tenant reference is impossible by constraint (foreign-key checks bypass RLS). ACL arrays must be non-empty (`CHECK`). A partial unique index allows reverts of content (A → B → A) but rejects a duplicate of live content. Deleting a document cascades to versions and chunks. Embeddings are stored later in a separate table because dimension depends on the model (ADR-002).
3. **Row-level security** is enabled and **forced** on every tenant table. One policy per command (permissive policies are OR-ed, so separate policies avoid accidental widening): SELECT, UPDATE and DELETE require tenant and ACL overlap; INSERT and UPDATE have an explicit `WITH CHECK` on the tenant. Versions inherit their document's visibility through an `EXISTS` subquery. `tenants` is readable only for the caller's own tenant and is not writable by the application.
4. **Identity** (`tenant_id`, `user_id`, `groups`) is written at the start of every transaction with `set_config(..., true)` (transaction-local) and read by `rag.app_tenant()` and `rag.app_groups()`, which **raise an error when the setting is missing or empty**, so the database fails closed. The identity comes from authentication (component 13), is validated against a restricted alphabet and never comes from request bodies or model output.
5. **Access layer.** Synchronous psycopg with `psycopg_pool.ConnectionPool`, executed in worker threads (`Database.run`), one identity-scoped transaction per unit of work: commit on success, rollback on any exception. Statement and idle-in-transaction timeouts are set per connection. The pool opens without waiting so the service starts when the database is down; readiness reports it.
6. **Migrations.** Forward-only `NNNN_name.sql` files run by `python -m rag_service.db.migrate` as `rag_owner`; contiguous numbering; SHA-256 checksum per migration recorded and verified (editing an applied migration is an error, as is an applied migration with no file); a PostgreSQL advisory lock serialises concurrent runners; each migration is one transaction and a failure is rolled back and not recorded; error messages never contain SQL text. In compose a one-shot `migrate` service runs before the API starts.
7. **Readiness** checks both connectivity and that the schema version equals the version this build expects (`SchemaVersionCheck`).
8. **Test discipline.** Isolation properties are asserted against the real schema as the restricted role; a guard test fails any future tenant table that lacks forced RLS or per-command policies; **mutation testing of the policies** (`scripts/mutation_db.py`) is part of the process, because layered defences mask each other in tests (see Rationale).

## Rationale

Executed evidence (details in Chapters 16 and 17): 26 integration tests on the schema, isolation and the data layer, 5 on the migration runner, 1 on the readiness check and 17 unit tests (identity validation, migration-file discovery, wiring); mutation testing of 15 injected defects in the migration SQL, identity validation, the pooled-transaction code and the runner, all detected after three rounds of strengthening. The first mutation run detected 12 of 15 and showed three tests passing for the wrong reason because a second layer masked the first: a foreign key hid a missing UPDATE `WITH CHECK`, a second policy function hid a missing-tenant fail-open, and an unaffected second setting hid a session-scoped tenant leak. A probe of the surviving case showed that PostgreSQL applies the SELECT policy to the new row only when the UPDATE reads a column; an UPDATE that reads no column moved a row to another tenant when the `WITH CHECK` was removed, so the UPDATE `WITH CHECK` is load-bearing. This matches the PostgreSQL documentation (SELECT policies apply in addition to UPDATE policies when the statement reads columns) [SRC-122]. The pool commits on normal exit and rolls back on exception, as documented and tested [SRC-123].

## Trade-offs

One thread per in-flight database call (bounded by the pool and the default thread pool); a hand-written migration runner to maintain and no down-migrations; RLS adds per-row policy evaluation cost and, with HNSW, the post-filter starvation measured in Chapters 8 and 13 (mitigations are in ADR-009); composite keys make keys wider; FORCE RLS means even the owner cannot read data without an identity, so administrative tasks need a deliberate path.

## Consequences

Every feature accesses data through `Database.run(identity, work)`. New tenant tables must follow the pattern (tenant in keys, forced RLS, four policies, explicit grants) or the guard test fails. Tenant provisioning is not an application operation (no INSERT policy on `tenants`): it needs a privileged admin path (OI-051). Compose now needs three passwords (superuser, owner, app).

## Security Considerations

The application role cannot create, alter or drop objects, cannot disable or alter RLS or policies, cannot assume the owner role, cannot write `tenants` or `schema_migrations` and has no `TRUNCATE` (which bypasses RLS). Identity inputs are validated and are never interpolated into SQL. Passwords come from the environment, are not logged and are scrubbed from error text. Residual risks: foreign-key checks bypass RLS (mitigated by composite keys); a role with `BYPASSRLS` or superuser bypasses everything (the bootstrap superuser exists only in the container and in tests); covert channels through constraint errors (unique violations reveal existence) are not eliminated; secrets in environment variables are weaker than managed identity (Azure, later); no row-level audit trail yet.

## Performance and Cost

No performance measurements were taken. Known costs: one extra statement per transaction (`set_config`), policy evaluation per row (ACL array overlap is not indexed; a GIN index on `acl_groups` is deferred until measured), pooled connections. Readiness opens fresh connections (about 18–55 ms observed, informal).

## Reversal Conditions

Move to async psycopg if the dev host and CI run a selector event loop and measured thread overhead matters; adopt Alembic or another tool if migrations need branching, autogeneration or down-migrations; add per-tenant schemas or databases for tenants whose isolation or scale needs exceed shared-schema RLS (ADR-006 tiers); revisit if PostgreSQL planner or RLS behaviour changes in newer versions (re-run the SQL and mutation suites).

## Evidence gaps

PG16 only (OI-036); small synthetic data, no concurrency or load tests, no RLS-with-ACL performance measurement on realistic sizes; tenant provisioning path not built; PostgreSQL documentation for FORCE/owner behaviour was read earlier at a different page (SRC-004) and re-verified by tests, not re-read; psycopg_pool read at documentation level and exercised by tests.

## References

SRC-004 (RLS), SRC-122 (CREATE POLICY), SRC-123 (psycopg_pool), `scripts/verify-sql/03-rls.sql`, `scripts/verify-sql/04-hybrid-fts-schema.sql`, ADR-001, ADR-006, ADR-009, ADR-011.

## Amendment (2026-11-09, ADR-016)

The policies in migration 0001 had no `TO` clause and therefore applied to PUBLIC; migration 0003 binds them to `rag_app`, and `test_no_policy_applies_to_public` guards against a repeat. Every later policy must name its role.

## Addendum 2026-11-09 — Known limitation: the identity setting is changeable by SQL run as `rag_app`

Found while writing Chapter 29 and verified on the real migrated schema (scratch database, two tenants with 1 and 3 documents): the identity read by the row policies (`app.tenant_id`, `app.user_id`, `app.groups`) is set by the application role itself with `set_config`, which `PUBLIC` may execute, so a single `SELECT` run as `rag_app` can switch the identity it is scoped to (a session scoped to the tenant with 1 document ran `SELECT o.n FROM (SELECT set_config('app.tenant_id', '<other tenant>', true)) s, LATERAL (SELECT count(*) AS n FROM rag.documents) o` and saw 3).

**What this does and does not mean.** The decision above protects against bugs in application filters and against forgotten predicates. It does **not** protect against SQL injection in the application role or against any feature that executes untrusted (for example model-written) SQL as that role. No such SQL exists in the repository today: all statements are parameterised.

**Required follow-ups (OI-069).** Never run untrusted SQL as `rag_app` (use a separate role without `EXECUTE` on `set_config`, on a separate database or replica); keep application SQL parameterised and review any dynamic SQL; evaluate hardening the identity mechanism (identity set only by a `SECURITY DEFINER` function verifying a signed token, or per-tenant roles) before any BI or user-SQL feature.
