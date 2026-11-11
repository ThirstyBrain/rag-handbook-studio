# ADR-016: Extraction, Chunking and the Worker's Content Access

## Status

Accepted — 2026-11-09 (implemented and verified on PostgreSQL 16 with the compose stack; POSIX resource limits not yet observed, see Evidence gaps).

## Context

Component 4 turns a staged raw file into chunks. Three things make it more dangerous than it looks:

1. **Files are hostile input.** PDF and Office parsers are large and have a long history of memory and CPU exhaustion. A malformed file must not be able to stop the worker, and a parser compromise must not be able to reach database credentials.
2. **The worker could not read content by design** (ADR-015, OI-052). Extraction needs to *write* chunks for a tenant, which looks like it needs the broad content access we refused to give the worker.
3. **Chunk quality decides retrieval quality** (ADR-003): sentences cut in half, tables detached from their headers and context-free chunks were all shown in Chapter 4.

## Requirements

A compromised or confused worker must stay inside one tenant and one staged version; hostile files must be rejected cheaply and *permanently* (no retry storms); chunks inherit the document's ACL; processing is idempotent per version and retry-safe; the chunker is deterministic, structure-aware and bounded; limits are configuration, not constants.

## Options Considered

- **A. Extract inside the API process.** Simple, no worker privileges. Rejected: a parser crash or stall takes down request serving, and the API process holds the broadest database role.
- **B. Give the worker a content-reading role** (`SELECT` on chunks and documents). Easiest. Rejected: it turns a worker compromise into a cross-tenant data read, undoing ADR-013 and ADR-015.
- **C. Narrow write path plus a sandboxed parser process (selected).** The worker may *write* chunks of a *staged* version of the tenant named by the job it holds, and mark that version failed. It cannot read chunk content, titles or hashes and cannot activate a version. Parsing happens in a child process with no credentials.
- **D. A separate extraction service in its own container.** The stronger isolation boundary (network policy, separate identity, independent scaling). Deferred: it adds a service to deploy and secure; the child-process boundary behind `Extractor` is the seam where it would plug in.

## Decision

1. **Database access (migration 0003).** Column-level grants: `rag_worker` reads `documents(tenant_id, document_id, status, acl_groups)` and `document_versions(tenant_id, document_id, version, state)`, may `UPDATE (state, extractor, failure_reason)` on versions, and may `INSERT`/`DELETE` chunks with `SELECT` on only the three key columns (PostgreSQL requires read rights for a `DELETE ... WHERE`, SRC-128). Row policies for `rag_worker`: tenant equals the transaction-local `app.tenant_id`, which the worker sets **from the job row it holds**; versions are updatable only while `staged` and only to `staged` or `failed`; chunks are insertable, selectable and deletable only for `staged` versions. Activation remains the indexing stage's job.
2. **Existing policies are bound to `rag_app`.** The 0001 policies had no `TO` clause, so they applied to PUBLIC (SRC-128). Permissive policies are OR-ed, so they would have widened every worker policy above (for example allowing chunk inserts into active versions). Found while designing this decision, fixed with `ALTER POLICY ... TO rag_app`, and now guarded by a test that fails if any policy in schema `rag` applies to PUBLIC.
3. **Sandboxed extraction.** A child process (`python -m rag_service.features.extraction.child`) receives the file on stdin and returns JSON blocks on stdout. It runs with an **empty environment** (no database URL, no keys), a scratch working directory, no stderr, a wall-clock timeout and output cap enforced by the parent (child killed), and on POSIX address-space, CPU and file-size rlimits set by the child before it touches the file (SRC-130). The parent treats the answer as untrusted data: shape, kinds, levels, pages, sizes and failure codes are validated and the text is cleaned again.
4. **Parsers (standard library plus one package).** Plain text, Markdown and HTML with the standard library; DOCX with `zipfile` and `xml.etree` (member count, declared total size, compression ratio and encryption checked before reading; DOCTYPE/ENTITY refused; depth capped; streaming parse; hidden `w:vanish` text and deleted tracked changes skipped); PDF with **pypdf 7.0.0** (BSD-3-Clause, no required dependencies on Python 3.11+, SRC-125). Encrypted PDFs are rejected, not opened. HTML drops script, style, template, noscript, head, svg, iframe and comments, and uses no attribute values as text.
5. **Text hygiene.** NUL (PostgreSQL text cannot hold it), other control characters, bidi overrides and isolates, BOM and the Unicode tag block are removed; lone surrogates are replaced; text is NFC-normalised. This is hygiene, not an injection defence: **visible hostile instructions remain data** (tested).
6. **Chunking (`structure-v1`).** Heading-delimited sections; sentences, code lines and table rows are the smallest units; a chunk never spans sections; section path is stored per chunk; oversized units are split at whitespace then by characters; a continuing table repeats its header row when it fits the headroom between target and maximum; overlap is whole trailing units of the same section within a budget; target 512, maximum 768, overlap 50 tokens (ADR-003 hypotheses, not findings). **Token counts are an estimate** (characters ÷ 4) behind a configuration value until the embedding model's tokenizer is fixed (component 5).
7. **Failure policy.** A file that cannot be processed (`Rejected` with a safe reason code such as `encrypted_pdf`, `malformed_docx`, `unsafe_xml`, `timeout`, `no_text`) marks the version `failed` with that code and ends the job as `dead` immediately. Infrastructure faults (database, storage, sandbox start-up) propagate and are retried with backoff. A job whose version is no longer staged, or whose document is gone or deleted, writes nothing and succeeds.
8. **Idempotence.** Re-running a job replaces the version's chunks in one transaction (delete, insert, record extractor); the result is identical for identical input and configuration.

## Rationale

Executed evidence (this repository, 2026-11-09, PostgreSQL 16, Python 3.14.2 on Windows): see the Quality Report. In summary: 91 new tests cover parsers, hostile files, the sandbox (a sleeping child, a flooding child, a crashing child, children that lie, a child that reports its environment), 21 chunker invariants and the worker's database boundary; the worker-boundary tests include another tenant's rows, active versions, content and title reads, and activation attempts. The mutation suite `scripts/mutation_extract.py` injects realistic defects into the safety code and policies; its result is recorded in the Quality Report. While designing the mutants one check turned out to be provably dead (a post-read size check, since zipfile never returns more than a member declares) and was removed rather than kept as untestable code; a lying-header archive was tested and ends as a CRC failure, which is behaviour observed on Python 3.14.2, not documented (SRC-129).

## Trade-offs

A child process per file costs a Python start-up (tens to hundreds of milliseconds, not measured here) and does not isolate the network or filesystem: a compromised parser could read what its OS user can read. The worker holds a write path to staged chunks, which is real power: a compromised worker could plant chunks (but only into staged versions of the tenant named by an identity it chose, so not into another tenant's rows other than by lying about the job's tenant: see Security). PDFs lose headings and tables (no layout analysis, no OCR). The character-based token estimate is crude for non-English text.

## Consequences

Component 5 (embeddings) and 6 (indexing) read staged chunks through the same tenant-scoped path and activate the version when indexing completes. The `Extractor` protocol is where a layout service or a separate extraction container replaces the child process. Chunker changes are migrations: `chunks.chunker` records the version.

## Security Considerations

The worker names the tenant by setting `app.tenant_id` from the job row; **the database cannot tell a truthful worker from a lying one**, so the boundary against a *compromised worker process* is the staged-only, one-tenant-at-a-time, write-mostly shape of its grants, not proof that it names the right tenant. What the design does guarantee: no content reads, no activation, no schema or policy changes, and a crash or stall of a parser costs only the child. Not addressed: network egress from the child, a filesystem jail or syscall filter (container-level controls in the infrastructure component), malware scanning, hidden-by-CSS HTML text (extracted and indexed; pinned by a test as a known gap), ACL changes after chunking (no ACL-update endpoint exists yet; when one is added it must update chunk ACLs in the same transaction), and timing side channels.

## Performance and Cost

No measurements were taken. Costs to expect: child start-up per file, whole-page content-stream parsing in pypdf (documented as memory-hungry, SRC-127), one transaction per version for chunk writes. Chunking itself is linear in text size. Chunk count drives embedding cost (ADR-003), so `chunk_max_per_version` (default 20,000) also bounds that cost.

## Reversal Conditions

Move extraction to its own container when untrusted PDF volume is high, when network or filesystem isolation is required by policy, or when the child-process start-up cost matters; replace pypdf or add a layout service when headings and tables in PDFs are needed for retrieval quality (golden-set evidence); move to model-tokenizer counts when the embedding model is fixed; reconsider the worker's write grants if a stricter "ingest-as-tenant" credential (per-job signed identity) becomes available.

## Evidence gaps

POSIX rlimit enforcement was not observed on this Windows host (test skipped here; see OI-053 for the container check); no throughput, memory or latency measurements; one unexplained failure of one API test on its first run after the schema changed, not reproduced in 7 repeated runs, with diagnostics added; DOCX heading detection recognises only the `Heading N` and `Title` style identifiers; no Azure Document Intelligence comparison; token estimator unvalidated against any real tokenizer.

## References

SRC-125 (pypdf 7.0.0 metadata), SRC-126 and SRC-127 (pypdf docs), SRC-128 (PostgreSQL CREATE POLICY), SRC-129 (zipfile), SRC-130 (resource), ADR-003, ADR-013, ADR-014, ADR-015, Chapters 3, 4 and 5.
