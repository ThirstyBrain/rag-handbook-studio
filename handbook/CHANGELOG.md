# Changelog

## [Unreleased]

### 2026-11-10 — B15: Chapters 30 (RAG Architecture Patterns) and 31 (Architecture Decision Records)
- Added `docs/chapters/30-rag-architecture-patterns.md`, `31-architecture-decision-records.md`, diagrams `30-pattern-landscape`, `30-pattern-selection`, `31-adr-lifecycle`, `31-adr-lint-flow`, sources SRC-206 to SRC-215 (S206-S215), glossary terms, OI-073 and OI-074, `scripts/validate-adrs.py`, and the generated `docs/09-Architecture-Decision-Records.md` (the catalogue did not exist before).
- Executed exercises `ch30_pattern_selection.py` (12 scenarios, invariants over 11,520 requirement sets, routing cost model; 7/7 mutants detected) and `ch31_adr_lint.py` (unit tests plus the real `adr/` directory; 15/15 mutants detected).
- **Finding (OI-073):** the linter found no structural errors in the 18 ADRs and 11 warnings of Accepted records citing still-Proposed ones (notably ADR-002 and ADR-006). No status was changed.

### 2026-11-09 — B14: Chapters 28 (Multimodal RAG) and 29 (Business Intelligence and Analytics)
- Added `docs/chapters/28-multimodal-rag.md`, `29-business-intelligence-and-analytics.md`, diagrams `28-multimodal-ingestion`, `28-caption-linking`, `29-sql-guard-layers`, `29-text-to-sql-flow`, sources SRC-192 to SRC-205 (S192-S205), glossary terms, OI-069 to OI-072.
- Executed exercises `ch28_multimodal.py` (synthetic; 12/12 injected defects detected) and `ch29_sql_guard.py` (**real PostgreSQL**; first complete run passed: 21 attacks no harm, text pre-check passed 10, tenant-setting attack leaks without a REVOKE; accuracy harness 71%/57%/100%; **mutation check NOT completed**, host disk full).
- **Finding (OI-069, ADR-013 addendum, Ch. 22 caveat):** SQL run as `rag_app` can change its own tenant identity via `set_config`; not exploitable by current code. **Blocker (OI-071):** `C:` has 0 GB free and the compose database returns I/O errors.

### 2026-11-09 — B13: Chapters 26 (Research and Academic Assistance) and 27 (Code and Developer Assistance)
- Added `docs/chapters/26-research-and-academic-assistance.md`, `27-code-and-developer-assistance.md`, diagrams `26-research-pipeline`, `26-citation-verification`, `27-code-chunking`, `27-code-context-assembly`, sources SRC-178 to SRC-191 (S178-S191), glossary terms, OI-066 to OI-068.
- Executed exercises `ch26_citation_verify.py` (synthetic; 7/7 injected defects detected; one pre-set criterion revised and disclosed) and `ch27_code_retrieval.py` (**measured on this repository's own Python**; 6/6 detected; AST chunking cuts through functions in 3.0% of chunks vs 73.7% for 40-line windows; retrieval benefit inconclusive, paired intervals span zero).
- Found: the reference implementation has no scholarly metadata, citation verification, retraction handling or code-aware extraction yet (OI-066, OI-067).

### 2026-11-09 — B12: Chapters 24 (Enterprise Knowledge Management) and 25 (Customer Support and AI Chatbots)
- Added `docs/chapters/24-enterprise-knowledge-management.md`, `25-customer-support-and-ai-chatbots.md`, diagrams `24-connector-sync-loop`, `24-permission-change-paths`, `25-support-decision-flow`, `25-handoff-flow`, sources SRC-170 to SRC-177 (S170-S177), glossary terms, OI-063 to OI-065.
- Executed exercises `ch24_connector_sync.py` (5/5 injected defects detected; design variants asserted as contrasts) and `ch25_support_policy.py` (5/5). Simulations with my own parameters; no real connector, bot or customer data.
- Found: the reference implementation has no connectors, ACL-update path, support bot, disclosure or handoff yet (OI-063, OI-064). Moffatt v. Air Canada and EU AI Act Article 50 are discussed from commentary and a reproduction respectively, with limits stated.

### 2026-11-09 — B11: Chapters 22 (RAG Security Architecture) and 23 (Enterprise AI Governance)
- Added `docs/chapters/22-rag-security-architecture.md`, `23-enterprise-ai-governance.md`, diagrams `22-threat-model-dfd`, `22-defense-in-depth`, `23-governance-lifecycle`, `23-erasure-propagation`, sources SRC-153 to SRC-169 (S153-S169; SRC-169 ISO/IEC 42001 recorded as NOT verified), glossary terms, OI-060 to OI-062.
- Executed exercises `ch22_security_controls.py` (18/18 injected defects detected; 17-payload attack corpus, 3,000 fuzz cases) and `ch23_governance.py` (16/16). Constructed attacks and illustrative policy only; no model, no legal advice.
- Found: the reference implementation has no authentication, quotas, access re-check, output policy, PII redaction, audit log or governance control plane yet (OI-060, OI-061). EU AI Act application dates were amended in July 2026 (Chapter 23 states what was verified and what was not).

### 2026-11-09 — B10: Chapters 20 (Performance and Cost Optimization) and 21 (Reliability and Production Failure Modes)
- Added `docs/chapters/20-performance-and-cost-optimization.md`, `21-reliability-and-production-failure-modes.md`, diagrams `20-latency-cost-levers`, `20-filtered-search-decision`, `21-retry-amplification`, `21-degradation-ladder`, sources SRC-143 to SRC-152 (S143-S152), glossary terms, OI-057 to OI-059.
- **Measured** pgvector benchmark `reference-implementation/evaluation/bench_pgvector.py` with results `evaluation/results/bench-pgvector-2026-11-09.json` (synthetic data, one host). Executed exercises `ch20_cost_latency_model.py` (7/7 mutants) and `ch21_resilience.py` (7/7).
- Found: Docker's default 64 MB /dev/shm broke a parallel HNSW build (compose `shm_size: 256m` added, unverified); job retry backoff has no jitter; no backups, deadlines, retry budget or load shedding in the reference implementation (OI-057, OI-058).

### 2026-11-09 — B9: Chapters 18 (RAG Evaluation) and 19 (Monitoring and LLMOps)
- Added `docs/chapters/18-rag-evaluation.md`, `19-monitoring-and-llmops.md`, diagrams `18-evaluation-system`, `18-judge-validation`, `19-observability-signals`, `19-burn-rate-alerting`, ADR-018 (Proposed), sources SRC-132 to SRC-142 (S132-S142), glossary terms, OI-055 and OI-056.
- Executed exercises: `ch18_evaluation.py` (13/13 injected defects detected) and `ch19_monitoring.py` (11/11). Data constructed or synthetic; no real model, judge, traffic or telemetry stack.
- Found while writing: the gateway's embed path reports `latency_ms` as a constant 0.0 (OI-055a).

### 2026-11-09 — M5 / component 5 (chunk embedding)
- Added `features/embedding/` (embedder over the gateway `embed` route, async bridge), migration `0004_chunk_embeddings.sql` (insert-only for the worker, select-only with chunk ACL for the app), content-derived chunk ids, vector write in the same transaction as the chunks, worker start-up policy and settings, compose wiring. ADR-017 accepted; SRC-131; OI-054.
- Tests: 44 new (28 unit, 16 integration); `scripts/mutation_embed.py` 28/28. Verified with the fake provider only; no real embedding model has been run. Chapter 16 §16.9 and diagram `16-embedding-flow`.

### 2026-11-09 — M5 / component 3 (document ingestion, object storage, job queue and worker)
- Added `features/ingestion/` (upload/list/get/delete API, content-type detection, object-store port with filesystem adapter, idempotent versioning, deletion outbox), `jobs/` (Postgres queue with SKIP LOCKED, leases, retries, dead state; handlers; worker process), `security/identity.py` (development-only identity, refused in production), migration `0002_ingestion_jobs.sql` and a third role `rag_worker` (job table only), compose `worker` service and `objects` volume.
- Tests: 70 new (41 unit, 17 API, 12 queue/handler) on real PostgreSQL; `scripts/mutation_ingest.py` 29/29; live stack verified. ADR-014 and ADR-015 accepted; Chapters 16 and 17 extended (diagram `16-ingestion-flow.mmd`). Registered SRC-124; opened OI-052. No new Python dependencies.

### 2026-11-09 — M5 / component 2 (database schema, roles, migrations)
- Added `database/migrations/0001_core_schema.sql` (tenants, documents, versions, chunks; forced RLS with per-command policies; fail-closed identity functions; least-privilege grants), `database/init/10-roles.sh` (rag_owner and rag_app), `rag_service/db/` (Identity, tenant-scoped pooled `Database`, migration runner with checksums and advisory lock), `SchemaVersionCheck` readiness, compose `migrate` service, API now connects as `rag_app`; `psycopg-pool` pinned.
- Tests: 17 unit + 32 integration on real PostgreSQL; `scripts/mutation_db.py` 15/15; `scripts/pg_test_env.py`. ADR-013 accepted (supersedes ADR-011 item 8); ADR-006 and ADR-011 updated. Chapters 16 and 17 extended (diagram `17-tenant-scoped-transaction.mmd`). Registered SRC-122, SRC-123; opened OI-051; OI-048 partly resolved.

### 2026-11-08 — M5 / cross-cutting: LLM gateway
- Added `features/llm/` (types, errors, config, port, gateway, deps, http mapping) with adapters `openai_compat` (httpx; OpenAI, Grok, Ollama, vLLM), `anthropic` (official SDK 2.6.0, lazy import) and `fake`; example config `config/llm-gateway.example.toml`; optional `docker-compose.llm.yml`; usage guide `features/llm/README.md`; `scripts/mutation_llm.py` (15/15 killed); tests: gateway, adapters (mocked HTTP), config, wiring, real-Ollama integration, opt-in live Claude.
- ADR-012 accepted. Chapters 16 and 17 extended (diagram `16-llm-gateway.mmd`). Registered SRC-118–121; opened OI-049, OI-050. Runtime dependencies added/pinned: anthropic and its httpx2 stack, httpx.

### 2026-11-08 — M5 / component 1 (foundation)
- Added `reference-implementation/` foundation: FastAPI app factory, settings, JSON logging with credential scrubbing, RFC 9457 errors, pure-ASGI middleware, events port, health feature (live/ready) with PostgreSQL probe, Dockerfiles, compose stack (PostgreSQL 16 + pgvector 0.8.7), pinned requirements, `scripts/check.py`, README, DEPENDENCIES.md; 30 tests passing (with DB), ruff/mypy-strict clean.
- ADR-011 (backend structure and foundation conventions) accepted. Registered SRC-117; opened OI-048. Chapters 16 and 17 started as living chapters (in progress).

### 2026-11-08 — M4 / B8 (M4 complete)
- Added Ch. 14 (Parent-Child and Hierarchical Retrieval) and Ch. 15 (Agentic RAG and Tool Usage); 4 diagram sources; executed exercises `ch14_parent_child.py` and `ch15_agent_harness.py` (both mutation-checked); new SQL verification `scripts/verify-sql/07-parent-child.sql`.
- ADR-010 (agentic retrieval and tool policy) drafted; ADR-003 amended for parent-child expansion. Registered SRC-106–116; glossary/references updated; opened OI-046, OI-047.

### 2026-11-08 — M4 / B7
- Added Ch. 12 (Re-Ranking Techniques) and Ch. 13 (Metadata Filtering); 4 diagram sources; executed exercises `ch12_reranking.py` (stand-in scorer; mutation-checked) and `ch13_filter_compiler.py` (mutation-checked); new SQL verification `scripts/verify-sql/06-metadata-filtering.sql` (selectivity sweep, generic-plan trap, partial index, list partitioning, typed vs JSONB estimates).
- ADR-008 (re-ranking policy) and ADR-009 (metadata filtering policy) drafted. Registered SRC-094–105; glossary/references updated; opened OI-043–045.

### 2026-11-07 — SQL verification (Docker started by user)
- Added `scripts/verify-sql.py` and `scripts/verify-sql/` (Dockerfile building pgvector v0.8.7 on a digest-pinned postgres:16-alpine; 5 SQL files with in-SQL assertions). All pass on PostgreSQL 16.12 + pgvector 0.8.7.
- Corrections caused by execution: Ch. 3 schema flaw (UNIQUE blocked reverts → partial unique index; Python exercise gained a revert case); Ch. 5 IVFFlat "planner skips index" claim replaced by observed behaviour; Ch. 5/8/9 simulations and `[I — not executed]` labels replaced with measured `[X]` results; Ch. 8 session-scope identity leak documented; Ch. 9 identifier tokenisation and stemming measured. ADR-001, ADR-004 (via Ch. 9), ADR-006 updated with measured evidence.
- Closed OI-013, OI-014, OI-020 (synthetic regime), OI-027; opened OI-036–038.

### 2026-11-07 — M4 / B6
- Added Ch. 10 (Query Expansion and Rewriting) and Ch. 11 (Multi-Query and Multi-Hop Retrieval); 5 diagram sources; executed exercises `ch10_query_transform.py` and `ch11_multi_query_multi_hop.py` (stand-in model steps; mutation-checked) plus shared helper `_toy_ir.py`.
- ADR-007 (query transformation and multi-step retrieval policy) drafted. Registered SRC-080–093; glossary/references updated; opened OI-039–042.

### 2026-11-07 — M3 / B5 (M3 complete)
- Added Ch. 8 (Enterprise RAG Architecture) and Ch. 9 (Hybrid Search); 4 diagram sources; executed exercises `ch08_authz_model.py` (mutation-checked) and `ch09_hybrid_search.py`.
- ADR-006 (multi-tenancy and isolation) drafted; ADR-004 amended (fusion evidence, lexical leg, analyzers). Ch. 6 reconciled with the original RRF paper (read in full).
- Registered SRC-064–079; glossary and references updated; opened OI-027–035. Fixed a Mermaid semicolon issue found by `validate-diagrams.py`.

### 2026-11-07 — M3 / B4
- Added Ch. 6 (Retrieval Mechanisms and Workflows) and Ch. 7 (RAG Architecture and Core Components); 5 diagram sources (retrieval workflow; logical, query-sequence, deployment, trust/failure boundaries).
- Added executed exercises `ch06_retrieval_pipeline.py` and `ch07_orchestrator_contracts.py` (with a 5-mutant check). ADR-005 drafted (Proposed, evidence gap).
- Registered SRC-053–063; glossary and references updated; opened OI-023–026; OI-006 partly resolved (OTel retrieval span status: Development).

### 2026-11-07 — M2 / B3 (M2 complete)
- Added Ch. 5 (Embeddings and Vector Databases) with store comparison, tenancy patterns, capacity planning, filtered-search analysis; exercise `ch05_ann_demo.py` (executed); 4 diagram sources.
- ADR-001 amended (Option C researched at doc level; decision unchanged). Registered SRC-039–052. Glossary/references updated. Opened OI-020–022.

### 2026-11-07 — M2 / B2
- Added Ch. 3 (Document Ingestion and Processing) and Ch. 4 (Text Chunking Strategies).
- Added exercises ch03_ingestion_idempotency.py, ch04_chunking_demo.py (executed); 3 diagram sources.
- ADR-003 finalized as accepted baseline. Registered SRC-030–038. Glossary and references updated. Ch. 1 §1.8 now cites SRC-028.
- Opened OI-014–019.

### 2026-11-07 — Tooling
- Installed `@mermaid-js/mermaid-cli` 12.2.0 under `scripts/tools/` (user-approved); added `scripts/validate-diagrams.py`. Ch. 1–2 marked complete.

### 2026-11-07 — M2 / B1
- Added Ch. 1 (Traditional LLM vs. RAG) and Ch. 2 (RAG Internals) in review status.
- Added diagram sources, `ch02_similarity_demo.py`, `scripts/build-handbook.py`, generated canonical handbook, glossary, references.
- Registered SRC-019–029; opened OI-009–013.

### 2026-11-07 — M1
- Registered 18 researched sources (SRC-001–018).
- ADR-001 revised to conditionally accepted; added ADR-002, ADR-003 (structure only), ADR-004.
- Added M1-ARCHITECTURE-AND-ROADMAP (reference architecture, comparison, version matrix, diagram inventory, roadmap).
- Recorded new open issues OI-002a, OI-006–008.

### 2026-11-07 — M0
- Initialized repository structure per CLAUDE.md §3.
- Added project-management artifacts (PRD, TOC, execution plan, progress, research register, quality report, open issues, milestones).
- Added ADR-001 (Proposed, unverified).
