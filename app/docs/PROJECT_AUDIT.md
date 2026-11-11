# Project audit: `rag-architecture-handbook`

Audited 2026-11-08 for the reading application in `ui-application2`. The handbook repository was treated as read-only throughout; nothing in it was created, changed or deleted. Exercise scripts were executed with `python -I -B` so no `__pycache__` was written into it.

## 1. Repository overview

*The Production-Grade RAG Architecture & Engineering Handbook* is a research-backed reference for architects and principal engineers. Its own `CLAUDE.md` defines the reader (about 13 years of enterprise engineering experience), the mission, and governance: research before authoring, evidence tags on every significant claim, no fabricated benchmarks, a 12-step teaching structure per topic.

| Path | Role |
|---|---|
| `docs/chapters/NN-slug.md` | Canonical chapter text, one file per chapter |
| `docs/RAG-Architecture-Handbook.md` | Generated concatenation of the chapters (`scripts/build-handbook.py`); not used by the app to avoid duplication |
| `docs/11-Glossary.md`, `docs/12-References.md` | Cumulative glossary table and reference table |
| `docs/assets/diagrams/*.mmd` | Mermaid sources of every chapter diagram |
| `docs/exercises/*.py` | Standard-library Python exercises behind `[X]` claims, plus helper `_toy_ir.py` |
| `adr/ADR-0NN-*.md` | Architecture decision records |
| `project-management/MASTER-TOC.md` | The 33-chapter plan with per-chapter status |
| `project-management/*` | PRD, milestones, progress, research register, quality report, open issues |
| `reference-implementation/*` | Empty scaffolding (`.gitkeep` only) |
| `scripts/` | Build, Mermaid validation, SQL verification (Docker + PostgreSQL) |

## 2. Content inventory (measured by the app's own parser)

| Item | Count | Notes |
|---|---|---|
| Planned chapters | 33 in 8 parts | From `MASTER-TOC.md` |
| Chapters on disk | 17 | 1–15 `complete`; 16–17 `IN PROGRESS` (both appeared during this audit, at 20:10) |
| Words in chapters | 64,714 | About 5 hours of reading at 220 wpm |
| ADRs | 11 | 3 Accepted, 8 Proposed (ADR-011 appeared during this audit) |
| Glossary terms | 124 | Each with chapter notes such as `[Ch. 2, 9]` |
| References | 112 | Table entries plus per-chapter lists for later chapters |
| Mermaid diagrams | 30 files, 32 inline blocks | Inline blocks duplicate the `.mmd` files |
| Exercises | 14 scripts, 18 runs | 4 scripts also have a cited `--mutants` variant |
| Evidence marks | 1,778 | S 1,102, E 322, X 246, N 37, V 31, I 23, A 17 |

## 3. Chapter and section structure

Every complete chapter follows the same 17–20 section skeleton (`N.1 Learning Objectives` … `N.17 Summary`, `References`), with `N.4 Core Concepts` holding the numbered `N.4.x` sub-topics. Headings carry their number in the text (`### 9.4.1 BM25`), so section ids are derived from the heading text and are stable across renders. The first line is always `# Chapter N — Title`.

## 4. Technical content types

- Prose with inline evidence tags: `[S67]`, `[X]`, `[E, S76]`; occasionally prose-y tags like `[E — formula text not verified …]` that are not machine-parseable and are rendered as text.
- GFM tables (option comparisons, fusion methods, status lists).
- Fenced code: `bash` (exercise runs), `sql`, `python`, `text` formulas, unlabelled blocks, and 32 `mermaid` blocks.
- Blockquote "Evidence legend" at the top of each chapter.
- Cross-references: "Chapter 6", "ADR-004", `docs/exercises/chNN_*.py`, `docs/assets/diagrams/*.mmd`.
- ADR sections: Status, Context, Requirements, Options, Decision, Rationale, Trade-offs, Consequences, Security, Performance and Cost, dated Amendments and Verifications, Evidence gaps, Reversal Conditions, References.

## 5. Existing functionality

- No end-user UI ships in the repository. `reference-implementation/frontend` is empty.
- A sibling folder, `ui-application`, contains an earlier Vite + React reader. It was not modified; `ui-application2` is a separate application.
- Tooling: `build-handbook.py` (concatenation), `validate-diagrams.py` (Mermaid CLI), `verify-sql.py` (PostgreSQL checks in Docker).
- No search, navigation or index exists in the repository beyond the Markdown TOC.

## 6. Content consumption workflows

1. Linear study: Part I → III in order, following each chapter's objectives and checkpoint.
2. Problem-driven lookup: jump to a technique (reranking, filtering) or a term.
3. Decision review: read an ADR, follow it to the chapters that amended it.
4. Verification: read a claim tagged `[X]`, inspect the script and its output.
5. Interview preparation: each chapter's "Interview Questions" section.

## 7. Navigation requirements derived from the content

- Part → chapter → numbered section hierarchy, with planned chapters visible but not clickable.
- In-chapter outline with H2 and H3 levels (25–34 sections per chapter).
- Links from mentions: chapters, ADRs, exercises, sources (`[S#]` → citation).
- Glossary → chapters where a term is defined; ADR → chapters that discuss it.

## 8. Integration approaches considered

| Option | Verdict |
|---|---|
| Copy Markdown into the app | Rejected: duplicates content and drifts |
| Read the generated `RAG-Architecture-Handbook.md` | Rejected: one huge file, generated, harder to map to routes |
| **Build-time glob imports of the canonical files through a read-only alias** | **Chosen.** One module (`src/content/source.ts`) knows the paths; every page renders the real files; editing a chapter shows up on reload |
| Runtime fetch from a content server | Rejected for MVP: adds a server for no reader benefit |

### Content mapping

| Source | Parsed by | UI |
|---|---|---|
| `docs/chapters/NN-*.md` | `parse/chapter.ts` | `/handbook/NN-slug`, contents, search, landing path |
| `MASTER-TOC.md` | `parse/toc.ts` | Parts, planned chapters, status |
| `adr/*.md` | `parse/adr.ts` | `/decisions/ADR-0NN` |
| `11-Glossary.md` | `parse/glossary.ts` | `/glossary` |
| `12-References.md` + chapter `## References` | `parse/glossary.ts` | `/references`, source popovers |
| `assets/diagrams/*.mmd` | `handbook.ts` | Architecture map |
| `exercises/*.py` + captured runs | `parse/exercise.ts`, `scripts/capture-exercises.mjs` | Exercise panels, `/exercises`, retrieval lab |

## 9. Implementation constraints

- The source is live: two chapters and one ADR appeared during the audit. The parser must tolerate new statuses (`IN PROGRESS`) and new files without code changes.
- Diagrams use Mermaid flowchart and sequence syntax; Mermaid is about 1 MB and must load lazily.
- Exercise output must come from real runs, not from the app. Python may be absent on a build machine.
- The retrieval demo in the repository (ch09 Part C) is a toy with a character-trigram stand-in for embeddings; it must be labelled as such.
- Chapters 18–33 (evaluation, security, governance and others) do not exist yet; the UI must not invent their content.

## 10. Risks and recommendations

| Risk | Mitigation in the app |
|---|---|
| Source structure drifts (new heading names, statuses) | Parsers are tolerant and unit-tested; an integration test parses the real repository on every run |
| A port of the toy retrieval engine diverges from the script | `engine.test.ts` parses the captured Python output and asserts identical top-3 and nDCG@3 for all 16 rows, and that the corpus still matches the script |
| Captured output goes stale after a script edit | Each capture stores the script's SHA-256; the panel warns when the hash differs |
| Bundle size (whole handbook in the client) | Content in its own cacheable chunk (275 kB gzipped); Mermaid and every route lazy-loaded |
| Unescaped HTML in Markdown | Output sanitised with DOMPurify; tested |
| A few `[S#]` ids may be missing from reference lists | The popover says so instead of failing |

Recommendation to the handbook: add `ADR-011` and chapters 16–17 to the reference table when they complete, and give prose-style evidence notes (`[E — …]`) a parseable form if they should become interactive.
