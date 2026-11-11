# Implementation plan and architecture decisions

## Stack

| Choice | Why |
|---|---|
| React 18 + TypeScript (strict, `noUncheckedIndexedAccess`) | Requested direction; strict types catch parser edge cases |
| Vite 5 | The content is local files; Vite's glob imports read them at build time with no server. Next.js would add a server runtime the product does not need |
| Plain CSS with custom properties | Tokens are the design system; Tailwind's defaults are what the brief asks to avoid |
| `marked` + `DOMPurify` | Small, fast GFM parser with custom renderers; sanitised output |
| `highlight.js` core with 7 languages | Only the languages the handbook uses |
| `mermaid` (lazy) | The handbook's diagrams are Mermaid; loaded on first diagram |
| Self-hosted Geist fonts | No third-party requests |
| Vitest + Testing Library + jsdom; ESLint + typescript-eslint | Unit, integration and UI interaction tests; lint |
| Tiny in-house router (`shared/router`) | Ten flat routes; a dependency would add more surface than it removes |

No animation library: CSS transitions and the View Transitions API cover the motion design.

## Structure (feature-first)

```
src/
  app/              shell: routes, header, footer, error boundary, 404, scroll restoration
  content/          the content layer
    source.ts       the ONLY module that knows handbook paths (glob imports)
    parse/          pure parsers: chapter, toc, adr, glossary+references, exercise, evidence, text
    handbook.ts     assembles the model once; lookups
    renderContext.ts what the Markdown renderer needs for cross-links
  design/           tokens, base, components, prose, code
  shared/
    markdown/       render.ts (Markdown → sanitised HTML), MarkdownBody (diagrams, copy, portals), mermaid, highlight
    router/ analytics/ logging/ storage/ hooks/ ui/
  features/
    landing/        hero + bands
    handbook/       contents page
    reader/         chapter page, outline, sidebar, reader bar, source popover, related chapters
    architecture/   stages (curation), map, stage detail
    playground/     domain/ (engine port, corpus, hybrid pipeline) + UI
    exercises/      exercise panel, exercises page
    decisions/ glossary/ references/ search/
  generated/        exercise-runs.json (written by scripts/capture-exercises.mjs)
scripts/capture-exercises.mjs
```

## Decisions

**UI-ADR-1: Read the canonical files at build time through a read-only alias.** `@handbook` → `../handbook`. Alternatives (copying content, reading the generated combined file, a content server) duplicate content or add infrastructure. Consequence: the whole handbook ships to the client in one cacheable chunk (788 kB, 275 kB gzipped). Reversal trigger: the handbook grows past roughly 2 MB of Markdown, at which point chapters should become per-route dynamic imports.

**UI-ADR-2: Parse in pure modules, render with string HTML, hydrate islands.** Chapters are rendered to sanitised HTML once and injected; interactive parts (exercise panels) mount into slots through React portals, and diagrams render lazily in place. This keeps 30-section chapters fast and avoids a React node per paragraph.

**UI-ADR-3: Exercise output is captured, never simulated.** `scripts/capture-exercises.mjs` runs every exercise and every variant a chapter cites, recording stdout, exit code, duration, interpreter version and the script's SHA-256. The panel compares the hash with the current source and warns when stale. Without Python the build keeps the previous capture.

**UI-ADR-4: The retrieval lab is a verified port, labelled as a toy.** The engine reproduces `ch09_hybrid_search.py` Part C. A unit test parses the captured Python output and asserts identical top-3 lists and nDCG@3 for all 16 rows, and that the corpus still matches the script. The UI says what it is (eight documents, trigram stand-in) and that it proves nothing about real data, as the chapter itself says.

**UI-ADR-5: Architecture-map curation is the only hand-written mapping.** `features/architecture/stages.ts` assigns chapters, diagram files and ADRs to stages. All descriptive text comes from the chapters. A test fails if a referenced chapter, diagram or ADR disappears.

**UI-ADR-6: Local search index.** About 820 passages (chapters, sections, terms, decisions, ADR sections, exercises, sources) indexed in memory on first open: AND semantics, last term as prefix, title boost, log-tf × idf. No service, works offline.

## Phases delivered

1. Repository audit → `PROJECT_AUDIT.md`
2. Skill discovery → `DESIGN_SKILL_AUDIT.md`
3. Reference audit in the browser → `REFERENCE_DESIGN_AUDIT.md`
4. Creative direction and tokens → `DESIGN_SYSTEM.md`
5. Content layer, renderer, exercise capture
6. Pages: landing, contents, reader, architecture, lab, exercises, decisions, glossary, references, search, 404
7. Tests, lint, type-check, build
8. Two browser refinement passes at six widths → `VALIDATION_REPORT.md`

## Code-generation checklist (from the user's engineering rules)

| Rule | Where |
|---|---|
| Error handling | `ErrorBoundary` per route; Mermaid failure falls back to source; storage never throws; capture script survives missing Python |
| Loading states | Route `Suspense` with `Loading`; diagrams show source while loading |
| Empty states | Glossary, references, contents filters, search, lab empty query, stage without diagrams, exercise without capture |
| Analytics | `shared/analytics/track.ts`: typed events, buffered, re-dispatched as `rag:analytics`, no network |
| Logging | `shared/logging/log.ts`: scoped, level-filtered |
| Unit tests | 67 tests across parsers, renderer, search, engine, stages, router, output classification, UI |
| No hardcoded content | All chapter, ADR, glossary, reference, diagram and exercise text comes from the handbook |
