# Project Progress

## Current Milestone

M5 - Reference Implementation (+ Ch. 16–17). **Components 1 (foundation), 2 (database schema, roles, migrations), 3 (document ingestion, object storage, job queue, worker) 4 (extraction and chunking, ADR-016) and 5 (chunk embedding, ADR-017) and the cross-cutting LLM gateway are built and verified.** M0–M4 complete (Ch. 1–15).

## Current Batch

**Handbook-first phase (user decision 2026-11-09):** complete Ch. 18–33 in batches B9–B16, then resume M5 components 6–20. B9–B16 (Ch. 18–33) are **complete** (Ch. 29's exercise mutation check is **unfinished**, see the blocker below). **The handbook-first phase is finished; next is M5 component 6** (after the owner resolves OI-071 if the database is needed). Remaining M8 material (cheat sheets, flashcards, mock interviews, docs/07 and docs/08) is tracked in OI-075.

## Completed Chapters

- Ch. 1–15 (see MASTER-TOC.md for per-chapter limitations)
- **Ch. 32 System Design Interview Preparation and Ch. 33 Advanced Interview Question Bank (B16, 2026-11-10)**: 17 scenarios (fixed structure: prompt, clarify, architecture, trade-offs, failure modes, probes, scoring focus, chapters) and 108 questions (chapter pointer, difficulty, answer, evidence tag); synthesis of Ch. 1–31 with **no new external research**; `docs/exercises/ch33_bank_lint.py` (structure, uniqueness, chapter pointers, source ids; 11/11 mutants; real run 0 findings); limitations in OI-075
- **Ch. 30 RAG Architecture Patterns and Ch. 31 Architecture Decision Records (B15, 2026-11-10)**: `ch30_pattern_selection.py` (12 scenarios, invariants over 11,520 requirement sets, routing cost model; 7/7 mutants) and `ch31_adr_lint.py` (real `adr/` directory; 15/15 mutants); new `scripts/validate-adrs.py` and generated `docs/09-Architecture-Decision-Records.md`; finding OI-073 (Accepted ADRs cite still-Proposed ADR-002/006 etc.; no status changed); limitations OI-074
- **Ch. 28 Multimodal RAG and Ch. 29 Business Intelligence and Analytics (B14, 2026-11-09)**: `ch28_multimodal.py` (synthetic; 12/12 mutants) and `ch29_sql_guard.py` (**real PostgreSQL**; first complete run passed; **mutation check NOT completed**); finding OI-069 (rag_app can change its tenant identity via set_config; ADR-013 addendum, Ch. 22 caveat); limitations OI-070, OI-071, OI-072
- **Ch. 26 Research and Academic Assistance and Ch. 27 Code and Developer Assistance (B13, 2026-11-09)**: executed exercises `ch26_citation_verify.py` (synthetic; 7/7 mutants; one pre-set criterion revised and disclosed) and `ch27_code_retrieval.py` (**measured on this repository's own Python**, snapshot 3dd9af6d14ed; 6/6 mutants; retrieval benefit inconclusive); limitations in OI-066, OI-067, OI-068
- **Ch. 24 Enterprise Knowledge Management and Ch. 25 Customer Support and AI Chatbots (B12, 2026-11-09)**: executed exercises `ch24_connector_sync.py` (5/5 mutants; design variants as contrasts) and `ch25_support_policy.py` (5/5); simulations with my parameters; Air Canada case from commentary only; Article 50 from a reproduction; limitations in OI-063, OI-064, OI-065
- **Ch. 22 RAG Security Architecture and Ch. 23 Enterprise AI Governance (B11, 2026-11-09)**: executed exercises `ch22_security_controls.py` (18/18 mutants; 17-payload attack corpus) and `ch23_governance.py` (16/16); not legal advice; ISO/IEC 42001 not verified; EU AI Act read in part (Digital Omnibus, time-sensitive); limitations in OI-060, OI-061, OI-062
- **Ch. 20 Performance and Cost Optimization and Ch. 21 Reliability and Production Failure Modes (B10, 2026-11-09)**: measured pgvector benchmark (synthetic data, one host) plus executed exercises `ch20_cost_latency_model.py` (7/7 mutants) and `ch21_resilience.py` (7/7); limitations in OI-057, OI-058, OI-059
- **Ch. 18 RAG Evaluation and Ch. 19 Monitoring and LLMOps (B9, 2026-11-09)**: executed exercises `ch18_evaluation.py` (13/13 mutants) and `ch19_monitoring.py` (11/11); synthetic/constructed data only; limitations in OI-055, OI-056

## Chapters In Progress (living chapters, written alongside the implementation)

- Ch. 16 Build a Complete Enterprise RAG Application: components 1–5 and the LLM gateway (§16.5–16.9; diagrams 16-llm-gateway, 16-ingestion-flow)
- Ch. 17 Production-Grade Code Implementation: foundation, gateway, migrations, tenant-scoped transactions, mutation-testing discipline, safe uploads, jobs without a broker (diagram 17-tenant-scoped-transaction)

## Pending Chapters

- None in the Ch. 1–33 plan (Ch. 16–17 remain living chapters until M5 ends). M8 extras still pending: cheat sheets, flashcards, mock interviews, `docs/07-System-Design-Interview-Guide.md`, `docs/08-Interview-Question-Bank.md` (OI-075)

## Completed Implementation Components

1. Foundation (ADR-011).
- Cross-cutting LLM gateway (ADR-012): routes → provider/model chains; Claude (official SDK), OpenAI-compatible (OpenAI, Grok, Ollama, vLLM), fake; retries, fallback, breaker, sensitivity policy, budgets, embedding-space guard.
2. Database schema, roles, migrations (ADR-013): `rag_owner`, `rag_app`; forced RLS; fail-closed identity; migration runner; tenant-scoped pooled `Database.run`.
3. **Document ingestion, object storage, job queue and worker (ADR-014, ADR-015)**: streamed upload API with size/content validation, idempotent versioning with race-safe writes, ACL rules, list/get/delete, object-store port with filesystem adapter (constructed, validated keys), Postgres job queue (SKIP LOCKED, leases, retries, dead state), `rag_worker` role limited to the job table, deletion outbox, worker process and compose services, development-only identity (refused in production). 29/29 mutation; live stack verified.

## In Progress Implementation Components

- None

## Pending Implementation Components

6. Vector + FTS indexing → 7. Hybrid retrieval → 8. Metadata/ACL filtering + recall-under-filter test → 9. Reranking → 10. Context assembly → 11. Grounded generation (via the gateway) → 12. Citation validation → 13. AuthN (replaces the dev identity) → 14. Tenant-isolation tests (end to end) → 15. Frontend → 16. Observability → 17. Evaluation → 18. Security tests → 19. Infrastructure (Bicep, Azure Blob adapter; authored only) → 20. CI/CD

4. **Extraction and chunking (ADR-016)**: sandboxed child-process parsers (text, Markdown, HTML, DOCX, PDF via pypdf) with empty environment, timeout and output cap; text hygiene; structure-aware `structure-v1` chunker; worker's narrow write path (migration 0003, column grants, staged-only policies; 0001 policies bound to `rag_app`); permanent-failure handling; idempotent re-chunking. 54/54 mutants killed.

5. **Chunk embedding (ADR-017)**: embedder over the gateway `embed` route inside the ingest job; chunks and vectors written in one transaction; `rag.chunk_embeddings` (worker insert-only, app select-only with chunk ACL; migration 0004); content-derived chunk ids; start-up refusal without a gateway. 28/28 mutants killed. **Verified with the fake provider only.**

## Completed Deliverables

- M0–M4 (Ch. 1–15) and B9–B15 (Ch. 18–31); ADRs 001–018 (9 Accepted, 9 Proposed; ADR-013 has an addendum); diagrams now 63 sources; exercises ch02–ch15, ch18–ch31; `evaluation/bench_pgvector.py` with measured results; 33 Mermaid sources; exercises ch02–ch15; `scripts/verify-sql.py` + 7 SQL files; canonical handbook (31 chapters incl. 2 in progress); glossary; references S1–S215; SRC-001–215 registered
- Reference implementation: components 1–4 and the LLM gateway; ADRs now 001–017

## Current Blockers

- **OI-071 (2026-11-09): the host's `C:` drive is full (0 GB free) and the compose PostgreSQL container returns I/O errors ('could not open file global/pg_filenode.map').** Docker Desktop's VM disk (`C:\Users\JACK\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, 43.7 GB) lives on C:. The database, API and worker containers are unusable until space is freed and Docker is restarted; the compose volumes may need integrity checks. I deleted nothing. **Required of the user:** free space on C: (or relocate Docker's disk image) and restart Docker Desktop. **Then:** (1) drop the scratch objects left by the aborted run (`DROP DATABASE` matching `ch29_%` and `DROP ROLE` matching `ch29_reader_%`); (2) re-run `python scripts/pg_test_env.py` and the full backend gate (`scripts/check.py`); (3) run `python -I docs/exercises/ch29_sql_guard.py --mutants` (needs `RAG_TEST_ADMIN_URL`) and record the result in QUALITY-REPORT.md; (4) verify OI-057's compose `shm_size` change by recreating the stack. Handbook work that does not need the database can continue.

**OI-071 update (2026-11-10, after the user started Docker):** the project database recovered from WAL; I dropped only the aborted run's scratch objects (`ch29_f309a67f`, `ch29_reader_f62f0081`); the full backend gate PASSED (ruff, format, mypy strict 59 files, 358 passed, 5 skipped; 3 more skips than before are the Ollama tests, Ollama not running). Then the `ch29_sql_guard.py --mutants` run hit the same `global/pg_filenode.map` I/O error: **C: is at 0 bytes free again and `docker_data.vhdx` is now 74.7 GB** (it was 43.7 GB when first recorded; it grows as tests create data and does not shrink by itself). I stopped `rag-reference-db-1` (my project's container only) to avoid writing into a full disk; nothing else was deleted. **Still open: the ch29 mutation check, OI-057 verification, and component 6.** Required of the user: free real space on C: (and ideally compact or relocate the Docker disk image to E:, which has 7 GB free, or trim unused images/volumes from other projects, which I will not touch), restart Docker, then `docker compose up -d db`. Check the volume again for corruption before relying on it; if it is unrecoverable, the schema is rebuilt by migrations (no valuable data lives in it).

## Session 2026-11-10 (later): figures and environment

- **Environment changed:** Docker Desktop, its VM disk, the WSL distro and the Puppeteer browser cache are gone; no local PostgreSQL. C: has 111 GB free, so the OI-071 disk-full cause no longer applies, but the database cannot run. User decision: components 6–20 may be **authored without running, labelled UNVERIFIED** (this deviates from CLAUDE.md 11.2/19; it must be recorded in QUALITY-REPORT.md for each such component). Not started yet.
- **Figures done:** `scripts/render-diagrams.py` (63 sources, SVG + PNG into `docs/assets/images/diagrams/`, generated); `scripts/embed-figures.py` wraps each chapter Mermaid block with the rendered image, a numbered caption (Figure C.K, original diagram) and a collapsed Mermaid source; `build-handbook.py` rewrites `../assets/` for the master. 62 figures embedded; `validate-diagrams.py` PASS with 0 problems (the Chapter 1 whitespace mismatch is fixed by syncing the `.mmd`). Headless Chrome reinstalled for mermaid-cli.
- **M8 extras done (generated, no new claims):** `scripts/build-interview-pack.py` builds `docs/07-System-Design-Interview-Guide.md`, `docs/08-Interview-Question-Bank.md`, `docs/flashcards/rag-flashcards.md` + `.tsv` (108 cards, parsed count equals chapter count), `docs/exercises/mock-interviews.md` (17 scenarios) and `docs/cheat-sheets/chapter-summaries.md` (31 chapter summaries; Ch. 16-17 have none). Still pending in M8: topic cheat sheets and quick-revision guides, independent review (OI-075).
- **Component 6 authored, UNVERIFIED (2026-11-10):** ADR-019 (Proposed); migration 0005 (one active version per document; worker may activate a version that has chunks and supersede an active one); `ChunkStore.activate_version` + pipeline step; `features/indexing` (`VectorIndexSpec` DDL/query-expression generator, `manage` CLI); integration tests edited for activation. Executed: ruff, format, mypy strict, 272 unit tests. Not executed: everything touching PostgreSQL (see QUALITY-REPORT). **Component 7 authored, UNVERIFIED (2026-11-10):** `features/retrieval` (RRF fusion, query validation, FTS + per-space vector legs filtered by tenant, ACL and active version, `POST /v1/search`, degradation to lexical-only reported in the response), 8 `retrieval_*` settings, 27 unit tests + 6 unexecuted integration tests (see QUALITY-REPORT). **Component 8 authored, UNVERIFIED (2026-11-10):** `features/retrieval/filters.py` (allow-listed filter compiler, wired into both legs and `POST /v1/search`), 14+ unit tests, `scripts/mutation_retrieval.py` (**47/47 mutants killed**, executed), plus unexecuted integration tests including the recall-under-filter test (synthetic data, my 0.9 threshold). **Component 9 authored (2026-11-10):** `features/reranking` (`Reranker` port, `GuardedReranker` with timeout + circuit breaker + first-stage fallback, local BM25 baseline, `apply_scores`), wired into `HybridSearch` behind `RAG_RERANK_ENABLED` (default off); 36 new unit tests; mutation check now **64/64** across components 6-9 (executed). A real cross-encoder and a measured N are NOT done. **Component 10 authored and unit-verified (2026-11-11):** `features/generation/context.py` (de-dup, per-document cap, token budget with estimated counts, opaque source ids S1.., delimited and neutralised passages), 19 unit tests, `scripts/mutation_context.py` 16/16 killed; 370 passed / 119 skipped overall. Next: component 11 (grounded generation via the gateway).
- **Not done:** open-licensed external images (none verified or added), measured-data charts, M5 components 6–20, M6, M7, M9.

## Known Technical Issues

- OI-001 git deferred by user (ask once at project end); OI-003 PDF tooling undecided; OI-007/011/041 abstract-level papers; OI-008 partly resolved; OI-010; OI-006 partly resolved; OI-036 SQL verified on PG16 only
- **(RESOLVED 2026-11-10, see session note above) validate-diagrams mismatch:** Chapter 1 block 1 differs from `docs/assets/diagrams/01-llm-vs-rag.mmd` only by whitespace around `<br>`; both files were modified externally between 20:13 and 20:19 on 2026-11-09 (not by me, likely an editor/formatter). Left untouched; fix by syncing the `.mmd` to the chapter block (or the reverse) and re-running the validator. All 93 other checks pass (47 sources render; all other chapter blocks match).
- **OI-073 Accepted ADRs cite still-Proposed ADR-002/006 etc. (owner decision needed; no status changed)**; OI-074 B15 limitations
- **OI-069 rag_app can change its tenant identity via set_config (High; ADR-013 addendum)**; OI-070 multimodal gaps; OI-071 disk-full blocker and unfinished ch29 mutation check; OI-072 B14 limitations
- OI-066 research-assistant gaps (no scholarly metadata, verifier, retraction handling); OI-067 code-assistance gaps (no code-aware extraction, symbol index, secret/licence scanning); OI-068 B13 limitations (synthetic ch26; ch27 small single-repo lexical measurement, inconclusive)
- OI-063 knowledge-management gaps (no connectors, ACL-update path, identity integration, staleness bound); OI-064 support-bot gaps (no generation/frontend/disclosure/handoff/quotas); OI-065 B12 limitations (simulation parameters; Air Canada decision not read; Article 50 via reproduction)
- OI-060 security gaps (no authN, no re-check/egress/quotas/PII redaction/audit in the app yet); OI-061 governance gaps (no register, DPIA, gates, audit log, erasure orchestration); OI-062 B11 limitations (EU AI Act and ISO 42001 not fully read; sources partial)
- OI-057 compose db /dev/shm (fix applied, unverified); OI-058 reliability gaps (no deadlines, retry budget, job-retry jitter, load shedding, backups/DR, fault injection); OI-059 B10 limitations (synthetic single-run benchmark, my simulation parameters, abstract prices)
- OI-055 observability gaps (embed latency reported as 0.0, no OTel/metrics/SLOs); OI-056 B9 limitations (no real judge/golden set/telemetry; sources read at abstract level; some general-knowledge methods unsourced)
- OI-049 gateway not verified live against Claude/OpenAI/Grok (no keys here); OI-050 no local embedding model installed; Ch. 10–12 and 15 exercises still use stand-ins (OI-040, 043, 046)
- OI-048 partly resolved; OI-051 component-2 limits
- **OI-054** component-5 gaps (no real embedding model run, token estimate, no re-embed path for active versions, no per-document sensitivity, no measurements)
- **OI-053** component-4 gaps (no container-level isolation, POSIX rlimits unobserved, no measurements, char-based token estimate, PDF flat text, no stable chunk ids)
- **OI-052** component-3 gaps: **no authentication (development identity only)**; worker cannot read content so extraction needs a design; no malware scanning, quotas or rate limits; Azure Blob adapter unwritten; no lease heartbeats; shared local volume; existence side channels; no load tests
- OI-012–052 (see OPEN-ISSUES)

## Research Pending

- Component 6: pgvector HNSW/IVFFlat/halfvec parameters and build behaviour (SRC-131 read at README level only), expression + partial indexes per embedding space, PostgreSQL full-text index use, activation rule (all chunks embedded and indexed), re-embedding path for active versions (indexer role, ADR-017 option D), recall under filtering (ADR-009).
- Later: Next.js and OTel current versions.

## Tests Executed

- Reference implementation (`scripts/check.py`, compose database): ruff, ruff format (94 files), mypy strict (59 source files) clean; 363 tests, 361 passed, 2 skipped (opt-in live Claude; POSIX rlimit test on Windows). Mutation: gateway 15/15, database 15/15, ingestion/jobs 29/29, extraction/chunking/worker boundary 54/54, embedding 28/28 (27/28 in the first full run; the survivor exposed a weak test, fixed and re-run for that mutant).
- Handbook: `validate-diagrams.py` pass; `build-handbook.py` 17 chapters (559k chars); `ch02`–`ch15` exercises and `verify-sql.py` not re-run (no changes to them; verify-sql does not cover migration 0004).

## Last Completed Task

2026-11-10: B16 authored (Ch. 32 scenarios, Ch. 33 question bank), `ch33_bank_lint.py` written and mutation-tested (11/11), handbook rebuilt (33 chapters, 1,140,765 chars), MASTER-TOC, OPEN-ISSUES (OI-075) and QUALITY-REPORT updated. Earlier: Component 5 (ADR-017) implemented and verified 2026-11-09.

## Next Exact Action

1. **Ask the user to resolve OI-071** (free disk space on C:, restart Docker) and then complete the verification steps listed under Current Blockers; also ask the user to decide the status of ADR-002 and ADR-006 (OI-073).
2. **B16 is done** (see Completed Chapters). Still to do for it: confirm `python -I scripts/validate-diagrams.py` completes (it exceeded a 2-minute foreground limit after the rebuild; Ch. 32–33 contain no diagrams, so no new result is expected beyond the known Chapter 1 whitespace mismatch); add glossary entries for interview terms if wanted. Later M8 batches: research reputable interview guidance (Tier 3, OI-075), independent review, cheat sheets, flashcards, mock interviews, and generate `docs/07` and `docs/08`.
3. After B16, resume M5 at component 6 (vector + full-text indexing, version activation; use `evaluation/bench_pgvector.py` as the first evidence; verify OI-057; address OI-069 in ADR/identity design), then components 7–20, and update Ch. 16–31 with real results. Wire `scripts/validate-adrs.py` into CI at component 20.
4. Optional user actions: (a) pull a local embedding model or provide a key (OI-050/054a); (b) run the live Claude test (OI-049); (c) run the rlimit test on Linux (OI-053b); (d) have counsel review Chapters 23 and 25 and the EU AI Act sources before any reliance (OI-062, OI-065); (e) decide how to sync the Chapter 1 diagram block with `01-llm-vs-rag.mmd` (see Known Technical Issues).
5. Do NOT run `git init`; ask the user once at the end (OI-001).

## Last Updated

2026-11-10
