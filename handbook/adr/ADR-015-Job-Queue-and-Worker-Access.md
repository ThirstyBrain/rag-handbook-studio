# ADR-015: Postgres-Backed Job Queue and Worker Access Model

## Status

Accepted — 2026-11-09 (implemented and verified on PostgreSQL 16.12; synthetic jobs, no load testing).

**Amended 2026-11-09 by ADR-016:** the statement below that the worker role has no access to content tables is superseded for chunk writes. `rag_worker` now has a narrow, column-level and state-gated write path to the chunks of staged versions (migration 0003); it still cannot read chunk content, titles or hashes and cannot activate a version.

## Context

Ingestion work (verifying and later extracting, chunking and indexing documents; deleting raw objects) must happen outside the request, survive crashes and retry safely. The worker needs to find work across all tenants, yet it must not become a way to read tenant content: ADR-013 established forced row-level security and a restricted application role.

## Requirements

At-least-once execution with bounded retries, backoff and a terminal failure state; no job executed by two workers at once; recovery from a crashed worker; cross-tenant claiming without cross-tenant data access; jobs created atomically with the data change that causes them (including deletion outboxes); no tenant data in error text; no new infrastructure for the reference implementation.

## Options Considered

- **A: In-process background tasks.** Simple; lost on crash, no retry, scales with the API.
- **B: Postgres table with `FOR UPDATE SKIP LOCKED`** (this ADR).
- **C: A broker (Azure Service Bus, RabbitMQ).** Production-grade; adds a service and a dual-write problem between the database and the broker (the Chapter 3 outbox pattern would be needed).
- **D: Worker uses the application role with a per-job tenant identity.** Rejected here: claiming requires seeing every tenant's jobs, which the tenant policy forbids.

## Decision

1. **Queue in PostgreSQL** (`rag.ingestion_jobs`): states `queued`, `running`, `succeeded`, `dead`, `cancelled`; attempts, a per-job attempt limit, `run_after`, a lease (`lease_expires_at`, `locked_by`) and `last_error`, which stores only an exception **class name**.
2. **Claiming** uses a single statement with `FOR UPDATE SKIP LOCKED` and sets the lease; a `running` job whose lease expired is claimable again and counts as an attempt; a job that has used all attempts when its lease expires is marked `dead`. Completion and failure apply only to the **lease holder**. Failure re-queues with exponential backoff or marks the job `dead` when attempts are used up.
3. **Third database role, `rag_worker`:** may `SELECT` and `UPDATE` the jobs table only; no privilege of any kind on content tables (verified through the privilege catalog and by refused statements). Row-level security on jobs has role-specific policies: the API role can insert and read **its own tenant's** jobs; the worker role can see all jobs because that is its function. The API role cannot update or delete jobs.
4. **Atomic creation:** the API inserts the job in the same transaction as the version it concerns, and the delete transaction inserts the `delete_objects` job (the outbox) with the object keys.
5. **Handlers work from the payload and the object store only** (they run as the worker role): `ingest_version` verifies that the raw object exists, is under the job's tenant prefix, and matches its recorded hash (extraction and chunking extend it in component 4); `delete_objects` validates every key against the job's tenant prefix **before deleting anything**, deletes, and cancels queued ingest jobs of the deleted document.
6. **Worker process:** `python -m rag_service.jobs.worker`, a separate compose service using the same image, stops cleanly on SIGTERM, logs job id, kind, attempt, state and duration only.

## Rationale

Executed evidence: six concurrent workers claimed 24 jobs exactly once each; future jobs wait and the oldest runs first; a worker that lost its lease can neither complete nor fail the job; failures back off (run_after pushed into the future), die after the last attempt and leave only the class name in storage even when the exception message contained a connection string; an expired lease is reclaimed; a job whose lease expires after its final attempt becomes `dead`; the worker role has no privilege on content tables and cannot insert or delete jobs; the API role sees and creates only its tenant's jobs and cannot update them; delete handlers refuse a payload containing another tenant's key without deleting anything. A first test of the worker privileges asserted the wrong error: PostgreSQL's planner pre-evaluates the (stable) policy function and fails before the privilege check, so the privilege catalog is the reliable assertion, with refused statements run after an identity is set.

Mutation testing of the component's policy code (`scripts/mutation_ingest.py`) detects 29 of 29 injected defects after one equivalent mutant was redesigned; a live run on the compose stack confirmed the upload, worker and deletion flow.

## Trade-offs

Polling latency (configurable interval) and database load from polling; at-least-once semantics mean handlers must be idempotent; no heartbeat to extend leases for long jobs (a long job needs a long lease or a heartbeat, to be added with extraction); no priority, rate limits or per-tenant fairness; ordering by `run_after` is best-effort under READ COMMITTED [SRC-124]; `SKIP LOCKED` removal would not break correctness but would reduce concurrency (not detectable by correctness tests); the worker sees every tenant's job payloads (object keys and hashes, never content).

## Consequences

New background work adds a `kind`, a handler and a migration for the `kind` check; handlers must be idempotent and tenant-prefix-safe; extraction (component 4) will need a deliberate design for reading content as a worker (see OI-052): the worker role has no content access by design.

## Security Considerations

Worker compromise exposes job metadata and object keys, not document text or other tables; error text never reaches storage or logs; payload keys are re-validated by the worker, so a forged payload cannot target another tenant's objects; the job table is subject to forced RLS like every tenant table.

## Performance and Cost

No measurements. Claiming is one indexed statement; the partial index covers only runnable states.

## Reversal Conditions

Move to a broker when throughput, fan-out or latency needs exceed polling, keeping the outbox pattern; add heartbeats, priorities and per-tenant fairness when workloads justify them.

## Evidence gaps

No load or soak test; no measurement of polling overhead; behaviour under database failover untested; long-running job leases untested.

## References

ADR-013, ADR-014, Chapter 3 (outbox pattern), SRC-124 (PostgreSQL 16 SELECT, locking clause: `SKIP LOCKED` skips rows that cannot be locked immediately and "can be used to avoid lock contention with multiple consumers accessing a queue-like table"; the page also warns that `ORDER BY` with a locking clause at READ COMMITTED can return rows slightly out of order, so job ordering is best-effort).
