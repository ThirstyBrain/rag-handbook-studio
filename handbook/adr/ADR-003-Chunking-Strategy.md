# ADR-003: Chunking Strategy

## Status

Accepted as a **baseline** — 2026-11-07. Structure and parameters are decided; numeric parameters (size, overlap) are starting points to be tuned by golden-set evaluation in M5. Evidence base: Chapter 4 research (SRC-028, 030, 031, 034, 035, 038).

## Context

Chunk boundaries determine what can be retrieved, cited and deleted. Constraints: embedding-model input limits (8,192 tokens on Azure's current embedding models [SRC-029]; 2K for the local `embeddinggemma` candidate [SRC-016]), a prompt budget for K chunks, and the need for stable chunk identity for citations and deletion propagation (Ch. 3).

## Requirements

Deterministic and versioned; structure-aware where structure exists; tables never lose headers; chunk metadata for citation, ACL inheritance, lineage; parent-child capable (Ch. 14); swappable behind an interface; any change evaluable and migratable via shadow index.

## Options Considered

- A: Fixed/token-based splitting. Simplest; structure-blind.
- B: Recursive splitting (paragraph → sentence → word) [SRC-038].
- C: Structure-aware (headings/layout roles) with table and code awareness [SRC-030].
- D: Semantic chunking. Evidence of inconsistent gains for its cost [SRC-034].
- E: Add-ons: LLM chunk context (vendor-reported gains [SRC-028]), late chunking (research-stage, needs long-context embedder [SRC-035]), parent-child (Ch. 14).

## Decision

1. **Baseline = C with B as the fallback** when structure is unreliable.
2. Size measured in **tokens of the embedding model's own tokenizer**, hard-capped below the model limit. Initial sweep centre: 512 tokens (Azure's documented starting point [SRC-031]); overlap swept over 0–25%, applied **only within a section**. These are hypotheses for M5 evaluation, not findings.
3. **Heading path + title are prepended to the embedding and keyword-index text**; clean text is stored separately for display and citation.
4. **Tables:** split between rows, repeat header row and heading path in every piece; keep small tables whole.
5. **Identity:** `chunk_id` derived from `(tenant, document, version, ordinal, content hash prefix)`; metadata per Ch. 4 §4.4.7, including `chunker_version` and `content_sha256`.
6. **Deferred experiments** (each requires a golden-set win to adopt): LLM chunk context, late chunking, semantic chunking, parent-child (planned for Ch. 14 / M5 step 8–10).
7. `Chunker` is a pure function behind an interface; every config or code change bumps `chunker_version` and triggers regression evaluation and shadow re-index.

## Rationale

Deterministic structure is cheap, explainable and avoids defects shown in the executed chunking demo (cut sentences, detached table headers, context-free chunks). Semantic chunking's cost was not justified by consistent gains in the one study reviewed [SRC-034]. Contextual retrieval's gains are vendor-reported [SRC-028] and require LLM calls per chunk, so it is an evaluated opt-in.

## Trade-offs

Depends on reliable structure extraction (layout service or Markdown source). Heading-prefix text raises tokens per chunk slightly. Overlap raises chunk count (vendor sample: +11.8% to +32.9% [SRC-031]). No semantic boundary detection means topic shifts inside long paragraphs are not detected.

## Consequences

Extraction must emit structure (roles/headings) not flat text. The golden dataset needs boundary, table and context-loss queries. Chunker changes are migrations. Every chunk stores lineage fields.

## Security Considerations

Chunks inherit parent ACLs; parent expansion re-checks ACL; chunk text is untrusted input to prompts; LLM-generated context (if adopted) is untrusted derived data and sends text to a model at ingest.

## Performance and Cost

Chunking is cheap; embedding and optional context generation dominate. Overlap and smaller chunks increase embedding and index cost. No measurements yet; M5 benchmark will report chunk counts and embedding tokens per corpus.

## Reversal Conditions

Revise if: golden-set recall on boundary-straddling or contextual queries is below target after tuning; structure extraction is unreliable for a major source class; an evaluated alternative (contextual, late, parent-child) beats baseline by a margin that justifies its cost; embedding model changes limit or tokenizer.

## Amendment 2026-11-08 (Chapter 14)

Parent-child expansion is adopted as an optional retrieval-time layer on top of this chunking baseline, not a change to it: children remain the embedded unit; parents live in a constraint-enforced relational store keyed by (section, document version); expansion is windowed and token-budgeted; ACL is evaluated per chunk on the expansion read; children are over-fetched from a measured distinct-parents distribution. Evidence: `scripts/verify-sql/07-parent-child.sql` and `docs/exercises/ch14_parent_child.py` (synthetic/toy; OI-047). Hierarchical summaries (RAPTOR-style, SRC-106) remain an evaluated option only.

## References

SRC-016, 028, 029, 030, 031, 034, 035, 038.

## Amendment (2026-11-09, implementation: ADR-016)

The baseline is implemented as chunker `structure-v1` in the reference implementation (heading-delimited sections, sentences, code lines and table rows as units, header-row repetition for continuing tables, overlap only within a section, section path on every chunk; sizes 512 target / 768 maximum / 50 overlap as configuration). Two deliberate deviations from the decision text, both recorded as open items: token counts are a **character-based estimate** (characters ÷ 4) until the embedding model's tokenizer is fixed (OI-053 e), and PDF input yields flat paragraphs per page because no layout service is used yet (OI-053 d), so the structure-aware behaviour applies fully to Markdown, HTML and Word input only. The numeric parameters remain hypotheses for golden-set evaluation (component 17).
