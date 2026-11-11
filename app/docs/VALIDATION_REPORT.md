# Test and validation report

Run on 2026-11-08, Windows 11, Node 24.13.1, Python 3.14.2.

## Automated checks (`npm run check`, exit 0)

| Check | Command | Result |
|---|---|---|
| Type-check | `tsc --noEmit` (strict, `noUncheckedIndexedAccess`) | Pass, 0 errors |
| Lint | `eslint .` (typescript-eslint, react-hooks) | Pass, 0 errors, 0 warnings |
| Tests | `vitest run` | **67 passed, 0 failed** across 9 files |
| Build | `vite build` | Pass. Entry 29 kB (10 kB gzip), vendor 238 kB (76 kB), handbook content 788 kB (275 kB), Mermaid and every route lazy |
| Exercise capture | `npm run exercises` | 18 runs of 14 scripts (including 4 `--mutants` variants), all exit 0 |

### Test coverage by area

| File | Tests | What it proves |
|---|---|---|
| `content/__tests__/parsers.test.ts` | 13 | Slugs, heading splitting around code fences, evidence tags, MASTER-TOC (including `IN PROGRESS`), chapter, ADR, glossary and reference parsing |
| `content/__tests__/handbook.test.ts` | 5 | Integration against the real repository: chapters, 8 parts, every ADR has a status and decision, glossary/references/diagrams/helpers, every exercise has a clean run |
| `shared/markdown/render.test.ts` | 8 | Evidence marks, ADR/chapter links only when targets exist, stable heading ids, code highlighting and copy, tables, Mermaid figures, exercise slots and variants, HTML sanitisation |
| `features/playground/domain/engine.test.ts` | 6 | The TypeScript port reproduces all 16 top-3 lists and nDCG@3 values from the captured Python run; corpus still matches the script; CRC32; BM25 and RRF behaviours |
| `features/search/searchIndex.test.ts` | 8 | Real index: all kinds indexed, multi-word, prefix, AND semantics, empty query, identifiers, snippets |
| `features/architecture/stages.test.ts` | 4 | Every curated chapter, diagram and ADR exists |
| `shared/router/router.test.ts` | 3 | Path matching, decoding, internal-link detection |
| `features/exercises/outputLines.test.ts` | 7 | Terminal line classification |
| `test/ui.test.tsx` | 13 | Interaction: exercise tabs with arrow keys and variants; glossary text and letter filters with analytics; lab judged vs free query, empty state, parameter reset; chapter rendering, evidence focus, 404; contents filter; ADR anatomy |

### Defects found by the tests and fixed

- `from __future__ import annotations` was listed as an exercise helper module (`__future__.py`). The helper pattern now excludes dunder modules.
- `Element.scrollTo` is missing in jsdom; the outline call is now optional-chained.

## Visual QA in the browser

Driven in the built-in browser against the dev server and the production build (`vite preview`). Screenshots were taken at each step; they are in the session transcript rather than saved as files.

### Pass 1 (1440 px, then 390 px)

| Area | Finding | Fix |
|---|---|---|
| Landing, explore band | 13 stages in a 4-column grid left an orphan and hid the two-path structure | Rebuilt as three labelled lanes (indexing, query, cross-cutting) under the copy |
| Landing, reading path | Part IV (chapters 16–17, which appeared mid-session) wrapped alone onto a new row | Grid now `auto-fit`, so 4 parts sit on one row at desktop |
| Exercise panel (split) | Copy button covered the first line of source | Moved into the tab bar row |
| Architecture map | Loop label clipped at the right edge; duplicate "BM25" term chip | Label moved and reworded; terms de-duplicated |
| Search | Typing straight after Ctrl K could be lost while the palette chunk loaded; input showed a boxy focus ring | Palette preloaded on idle; ring removed inside the palette (the field already shows focus) |
| Reader bar (mobile) | Showed "12.1 Learning Objectives" before the reader had scrolled | Scroll-spy starts empty, so the bar shows the chapter title |
| Status | Chapters 16–17 are `IN PROGRESS` in MASTER-TOC but were counted as written | New status parsed; amber notice in the chapter header, amber cells on the progress spine, honest counts on landing and contents |

### Pass 2 (1280, 1024, 768, 390, 360 px; production build)

| Area | Finding | Fix |
|---|---|---|
| Decisions at 360 px | Page scroll width 2,716 px: the horizontal ADR strip pushed the grid open | `min-width: 0` on the grid child; current ADR scrolled into view in the strip |
| Contrast | `--faint` text (rank numbers, minutes) was 2.81:1 | Darkened to `#666F7F` (4.59:1 on paper, 5.07:1 on white); decorative chapter numerals and glossary letters now use it too |
| All routes at 360 px | After the fix, scroll width equals viewport width on all 10 routes checked | — |

### Verified behaviours

- Landing: bench runs the real port; presets switch rankings with drawn connectors; nDCG@3 shown for judged queries.
- Reader: three-column layout ≥1280, two columns at 1024–1279, single column with sticky section bar and bottom sheet below 1024; outline scroll-spy and progress; Mermaid renders (state `ready`); tables scroll inside their container; exercise panel shows real output.
- Search: Ctrl K, typing, arrow keys and Enter navigated to a glossary anchor.
- Architecture: stage selection, diagram tabs, keyboard roving focus.
- Lab: four rankings with scores and per-term BM25 contributions; parameter sliders; reset.
- Console: no errors on the production build.

## Round 3: content fidelity (after user report of missing code, output and diagrams)

| Finding | Cause | Fix |
|---|---|---|
| Chapters 4, 12, 13, 14, 15 showed no exercise code or output | Their exercises are cited in prose ("Executed: `python -I …ch12_reranking.py --mutants`"), not in a run block; the placement logic skipped any file mentioned with `python -I` and then waited for a run block that never came | Placement planned from the Markdown tokens: run blocks are replaced in place; otherwise the panel goes after the "Executed:" / "Run:" paragraph (else the first mention), with the cited variant preselected |
| Code and output were behind tabs in chapters | Reader used the tabbed panel | Reader now shows source and the full output together (side by side when the panel is wide, stacked in the reading column) |
| Long output was collapsed after 28 lines | "Show all" toggle | Removed: the full captured output is always shown |
| Diagrams drew only when scrolled near; hidden tabs, fast scrolling, find-in-page or print could show raw Mermaid source | IntersectionObserver-triggered rendering | Diagrams render on mount in document order |
| Landing bands could stay invisible if the reveal observer never fired | Content hidden by default | Content visible by default; only below-the-fold bands animate, with a 4 s safety net |

New permanent test `content/__tests__/fidelity.test.ts` (68 tests, 4 per chapter): every paragraph, list item, heading and table cell from the Markdown appears in the rendered page; heading, table, list-item and callout counts match; every Mermaid block becomes a diagram and every other code block a highlighted block; every cited exercise gets a panel with a captured run. Total suite: **135 tests passing**.

Browser sweep of all 17 chapters (dev server, after the fix): 32/32 inline diagrams `ready`, 0 errors; all 60 diagram sources (inline + `.mmd`) render to SVG through the app's Mermaid module; 15 exercise panels across chapters 2–15 (chapter 8 shows two), each with source and output; table counts equal the source; no horizontal overflow. Chapters 1, 16 and 17 cite no exercise; 16 and 17 have no code or diagrams in their source yet.

## Round 4: reference-driven redesign (2026-11-09)

Rebuilt the landing hero from the reference poster and rethemed every page through the token layer. Browser passes at 1440, 1280 and 390 px (plus a 390 px overflow sweep of all routes):

| Pass | Finding | Fix |
|---|---|---|
| 1 Composition | Pipeline labels broke mid-word ("Docume nts") | Wider visual column, no forced word breaks; labels sit on one line like the reference |
| 1 | Confidence banner squeezed into the copy column; hero 1,221 px tall | Banner spans its own row at half the hero width over the navy waves; tightened spacing (hero now 1,053 px at 1440) |
| 1 | Teal wave behind the preview too faint; CTAs wrapped | Stronger wave gradients; CTA sizing adjusted so both sit on one row |
| 1 | Nav icons rendered at 7 px | SVGs no longer shrink in flex rows (global rule) |
| 2 Craft | Page-head band ended in a hard blue edge | Band fades into ivory |
| 2 | Feature CSS loads after the theme layer and overrode it | Feature-targeted theme rules raised in specificity |
| 3 Interaction | Hero headline read as "The RAGArchitectureHandbook" to assistive tech | Spaces between the line spans |
| 3 | Duplicate glossary terms (the handbook now defines some twice) collided on keys and anchors | Both entries kept; repeats get unique slugs (tested) |
| 3 | New handbook scripts (ch18–ch23) had no captured output | Captured: 20 scripts, 27 runs, all exit 0 |

Verified: no horizontal overflow on 10 routes at 390 px; zero console errors across 9 routes after a clean reload; search returns real results (including ADR-013, added to the handbook today); Exercises page lists 118+ real checkpoint questions with per-device progress; `npm run check` passes with 152 tests.

The five named design skills (UI UX Pro Max, Taste Skill, Hallmark, Impeccable, Better-UI) are still not installed; the reference image was the design source.

## Not verified

- Screen-reader output (NVDA, VoiceOver) was not tested; semantics were checked in the accessibility tree only.
- Safari and Firefox were not tested; the View Transitions API is used only where available.
- Lighthouse or bundle performance budgets were not run.
- Exercise output is as captured on this machine; a different Python version could print differently.
