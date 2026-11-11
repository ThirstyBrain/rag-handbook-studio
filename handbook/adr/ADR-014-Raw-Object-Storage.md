# ADR-014: Raw Object Storage Port and Filesystem Adapter

## Status

Accepted — 2026-11-09 (filesystem adapter implemented and verified; the Azure Blob adapter is deferred to the infrastructure component, where it can be tested against Azurite or a real account).

## Context

Ingestion must keep the original uploaded bytes (Chapter 3: re-extraction, audit, deletion) outside the relational database, tenant-separated, tamper-evident and deletable. The implementation runs locally with no paid service and is deployed to Azure (ADR-001). Objects can be hostile files; their keys must never be influenced by clients.

## Requirements

Immutable, content-addressed objects; a key space that cannot be abused for path traversal or cross-tenant access; idempotent writes; integrity verification; deletion that removes exactly one document's data and never another's; atomic writes (no partial reads); testable offline; an adapter boundary so Azure Blob can replace the local store.

## Options Considered

- **A: Store files in PostgreSQL** (`bytea`/large objects). Simple and transactional, but bloats the database and backups and makes large files costly.
- **B: Filesystem behind a port** (this ADR).
- **C: MinIO (S3-compatible) in compose.** Closer to cloud behaviour, adds a service and an SDK; not researched in this repository.
- **D: Azure Blob Storage with the Azurite emulator.** The production target; needs the Azure SDK and was not available to test here.

## Decision

1. An `ObjectStore` port (`put`, `exists`, `sha256`, `open`, `delete`) with a **filesystem adapter** now; Azure Blob later (same port, tested against Azurite).
2. **Constructed keys only:** `tenants/<tenant uuid>/<document uuid>/<sha256>`. Every key is validated against that exact pattern (anchored, lowercase hex, no extra path) before use, and the resolved path must stay inside the storage root. Client-supplied names (`source_id`, file names) are data stored in the database and never become path components.
3. **Content-addressed within a document, never shared across documents.** Deleting a document deletes exactly the keys derived from its versions, so identical content in two documents cannot cause cross-document deletion.
4. **Atomic, verified writes:** stream to a temporary file in the target directory while hashing, reject a hash mismatch, then atomically rename; existing objects are never overwritten.
5. **Object first, rows second:** the upload stores the object before the database transaction commits, so a job can never point at a missing object; objects stored for a discarded plan (a lost race, a failed write for a new document) are deleted.
6. **Deletion is an outbox:** the delete transaction removes the rows and enqueues a `delete_objects` job (ADR-015) carrying the keys; the worker deletes them, retries on failure, and refuses any key outside the job's tenant prefix.
7. Upload validation (media.py): size cap enforced on the stream; content type detected from bytes and required to agree with the declared type; allow-list of text, Markdown, HTML, PDF and declared Word documents.

## Rationale

Executed evidence: unit tests for key validation (traversal, absolute paths, uppercase, trailing path, wrong length), hash-mismatch rejection with no leftover temporary files, idempotent put, per-tenant separation; integration tests that hostile `source_id` values (`../../etc/passwd`, backslashes, newlines, 1000 characters) only ever produce files named by 64-hex hashes under `tenants/`; that rejected uploads leave no object; that concurrent identical uploads leave exactly one object; and that deleting one document never removes another's identical content. A weakness in my first content check was found by a test (`\x7fELF` passed as text) and fixed (control characters rejected).

Mutation testing of the component's policy code (`scripts/mutation_ingest.py`) detects 29 of 29 injected defects after one equivalent mutant was redesigned; a live run on the compose stack confirmed the upload, worker and deletion flow.

## Trade-offs

A local directory is not durable or shared across replicas (one named volume shared by the API and worker in compose); no deduplication across documents (storage cost); no virus scanning, quotas or encryption at rest yet; the filesystem adapter performs blocking I/O in worker threads.

## Consequences

Components 4+ read raw bytes only through the port. The infrastructure component adds the Azure Blob adapter and moves the volume to managed storage with encryption at rest and managed-identity access.

## Security Considerations

No client-controlled path components; tenant prefix enforced on every deletion key; media sniffing is a first filter only (extraction must treat files as hostile and run isolated); size limit bounds memory and disk use per request; objects are immutable. Not yet addressed: malware scanning, content-disclosure through error messages is avoided but timing differences are not analysed, quota per tenant, encryption at rest.

## Performance and Cost

Streaming with a one-megabyte spool; no benchmarks were taken. Storage cost grows with per-document duplication of identical content.

## Reversal Conditions

Move to managed blob storage for any shared or durable deployment; adopt cross-document deduplication only with reference counting; reconsider if upload sizes exceed the spool and thread model.

## Evidence gaps

Azure Blob adapter unwritten and untested; no malware scanning; no load test of uploads; media detection reads only the first 8 KiB and does not parse containers.

## References

SRC-004 (RLS, for the tenant model), ADR-001, ADR-006, ADR-013, Chapter 3.
