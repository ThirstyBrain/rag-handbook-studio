# Master Table of Contents

Source: Master Prompt §4 (33 chapters, 8 parts). Chapter files live in `docs/chapters/` as `NN-slug.md`. Status values: `pending` | `researching` | `drafting` | `review` | `complete`.

Batch size is 2–3 chapters (CLAUDE.md §5.1). Milestone mapping follows CLAUDE.md §4.

## Part I — RAG Fundamentals (M2)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 1 | Traditional LLM vs. RAG | B1 | complete (with recorded limitations OI-010, OI-011) |
| 2 | RAG Internals (tokenization, embeddings, similarity) | B1 | complete (with recorded limitations OI-011–013) |
| 3 | Document Ingestion and Processing | B2 | complete (limitations OI-014–016) |
| 4 | Text Chunking Strategies | B2 | complete (limitations OI-011, OI-017) |
| 5 | Embeddings and Vector Databases | B3 | complete (limitations OI-020–022) |

## Part II — Retrieval and Architecture (M3)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 6 | Retrieval Mechanisms and Workflows | B4 | complete (limitations OI-023, OI-025) |
| 7 | RAG Architecture and Core Components | B4 | complete (limitations OI-024–026) |
| 8 | Enterprise RAG Architecture | B5 | complete (limitations OI-027–029, OI-032–033) |

## Part III — Advanced RAG Techniques (M4)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 9 | Hybrid Search | B5 | complete (limitations OI-027, OI-030, OI-031, OI-034) |
| 10 | Query Expansion and Rewriting | B6 | complete (limitations OI-040, OI-041, OI-011) |
| 11 | Multi-Query and Multi-Hop Retrieval | B6 | complete (limitations OI-040–042, OI-011) |
| 12 | Re-Ranking Techniques | B7 | complete (limitations OI-043, OI-011) |
| 13 | Metadata Filtering | B7 | complete (limitations OI-044, OI-045) |
| 14 | Parent-Child and Hierarchical Retrieval | B8 | complete (limitations OI-047, OI-011) |
| 15 | Agentic RAG and Tool Usage | B8 | complete (limitations OI-046, OI-040) |

## Part IV — Implementation and Production Engineering (M5, M6)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 16 | Build a Complete Enterprise RAG Application | M5 | IN PROGRESS (living chapter; components 1–5 of 20 and the LLM gateway documented) |
| 17 | Production-Grade Code Implementation | M5 | IN PROGRESS (living chapter; foundation, gateway, tenant-scoped transactions, safe uploads, jobs, hostile-file parsing and narrow worker access documented) |

## Part V — Evaluation, Observability, Optimization (M6)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 18 | RAG Evaluation | B9 | COMPLETE with limitations (2026-11-09; no real judge, golden set or pipeline evaluated; see OI-056) |
| 19 | Monitoring and LLMOps | B9 | COMPLETE with limitations (2026-11-09; no real telemetry stack or traffic; OI-055, OI-056) |
| 20 | Performance and Cost Optimization | B10 | COMPLETE with limitations (2026-11-09; measured numbers are synthetic data on one host; OI-057, OI-059) |
| 21 | Reliability and Production Failure Modes | B10 | COMPLETE with limitations (2026-11-09; simulation with my parameters, no fault injection or restore drill run; OI-058, OI-059) |

## Part VI — Security and Governance (M6)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 22 | RAG Security Architecture | B11 | COMPLETE with limitations (2026-11-09; deterministic controls tested on constructed attacks, no model-based attack measurement; OI-060, OI-062) |
| 23 | Enterprise AI Governance | B11 | COMPLETE with limitations (2026-11-09; not legal advice; ISO/IEC 42001 not verified; EU AI Act read only in part and time-sensitive; OI-061, OI-062) |

## Part VII — Real-World Applications (M7)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 24 | Enterprise Knowledge Management | B12 | COMPLETE with limitations (2026-11-09; simulation with my parameters, no real connector; Azure ACL features are preview; OI-063, OI-065) |
| 25 | Customer Support and AI Chatbots | B12 | COMPLETE with limitations (2026-11-09; synthetic simulation with assumed calibration; Air Canada case from commentary only; not legal advice; OI-064, OI-065) |
| 26 | Research and Academic Assistance | B13 | COMPLETE with limitations (2026-11-09; synthetic index and citations; real-model fabrication rates from a 2023 study only; OI-066, OI-068) |
| 27 | Code and Developer Assistance | B13 | COMPLETE with limitations (2026-11-09; measured on one small Python code base, lexical retrieval, inconclusive retrieval benefit; OI-067, OI-068) |
| 28 | Multimodal RAG | B14 | COMPLETE with limitations (2026-11-09; synthetic layouts/transcripts, abstract prices, one vendor's token rule; OI-070, OI-072) |
| 29 | Business Intelligence and Analytics | B14 | COMPLETE with limitations (2026-11-09; real PostgreSQL run passed but **mutation check NOT completed** because the host disk filled; tenant-setting finding about rag_app; OI-069, OI-071, OI-072) |

## Part VIII — Architecture Decision Frameworks (M8)

| # | Chapter | Batch | Status |
|---|---------|-------|--------|
| 30 | RAG Architecture Patterns | B15 | COMPLETE with limitations (2026-11-10; a decision procedure and cost model were executed, no pattern was built or measured; paper claims are abstract-level; OI-074) |
| 31 | Architecture Decision Records | B15 | COMPLETE with limitations (2026-11-10; linter run on the real adr/ directory; Accepted-cites-Proposed finding OI-073; Y-statement format not read; OI-074) |
| 32 | System Design Interview Preparation (15–25 scenarios) | B16 | COMPLETE with limitations (2026-11-10; 17 scenarios synthesised from Ch. 1–31, structure linted; no external interview guidance researched; OI-075) |
| 33 | Advanced Interview Question Bank (100+ questions) | B16 | COMPLETE with limitations (2026-11-10; 108 questions linted, 11/11 mutants; answers not independently reviewed; OI-075) |

## Chapter → Supporting Document Mapping

| Supporting document | Chapters |
|---|---|
| `00-Executive-Overview.md` | Synthesis, written after Part III |
| `01-RAG-Fundamentals.md` | 1–5 |
| `02-RAG-Architecture.md` | 6–8 |
| `03-Advanced-RAG.md` | 9–15 |
| `04-Production-Implementation.md` | 16–17 |
| `05-Security-and-Governance.md` | 22–23 |
| `06-Evaluation-and-LLMOps.md` | 18–21 |
| `07-System-Design-Interview-Guide.md` | 32 |
| `08-Interview-Question-Bank.md` | 33 |
| `09-Architecture-Decision-Records.md` | 31 + `adr/` |
| `10-Production-Readiness-Checklist.md` | M6 |
| `11-Glossary.md`, `12-References.md` | Cumulative |

## Mandatory Diagram Inventory (Master Prompt §6)

Tracked in M1. 20 required diagrams: LLM vs RAG; end-to-end architecture; ingestion pipeline; chunking strategies; embedding generation; vector indexing; retrieval workflow; hybrid search; query rewriting; multi-query; reranking; parent-child; agentic RAG; multi-tenant architecture; security architecture; production deployment; evaluation pipeline; observability architecture; CI/CD; complete reference implementation.

## Per-Chapter Teaching Structure

Every major topic follows the 12-step structure in Master Prompt §7 (problem → production relevance → internals → architecture → example → implementation → trade-offs → failure modes → production considerations → decision → interview prep → checkpoint), mapped onto the 20-section structure in CLAUDE.md §7.1.
