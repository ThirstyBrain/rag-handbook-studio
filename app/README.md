# RAG Architecture Handbook: reading application

An interactive reading interface for [`../handbook`](../handbook). Every page is rendered from the handbook's own Markdown, ADRs, diagrams and exercise scripts at build time; the handbook folder is only ever read.

## Run

```bash
npm install
npm run dev          # http://localhost:5180
npm test             # 67 unit, integration and UI tests (Vitest)
npm run lint
npm run typecheck
npm run build        # type-check + production build into dist/
npm run check        # all of the above
npm run exercises    # re-run the handbook's Python exercises and record their output
```

The handbook lives in `../handbook` (this monorepo). Its path is set once, as the `@handbook` alias in `vite.config.ts`.

## What's inside

| Route | What it does |
|---|---|
| `/` | Masthead and a live hybrid-retrieval bench, reading path by part, architecture lanes, evidence totals, an exercise with source and real output, the decision ledger |
| `/handbook` | All 33 chapters by part: complete, in progress and planned, with a progress spine and filters |
| `/handbook/:slug` | The reader: chapter list, article, outline with scroll-spy, reading progress, evidence highlighter, source popovers, Mermaid diagrams, highlighted code with copy, exercise panels, connected chapters and decisions, `[` / `]` to move between chapters |
| `/architecture` | Blueprint of the indexing and query paths; each stage opens the handbook's diagrams, chapters, ADRs and terms |
| `/lab` | The ch09 toy pipeline in the browser: BM25, trigram stand-in, RRF and min–max fusion, per-term explanations, nDCG@3, adjustable parameters |
| `/exercises` | Every exercise script beside its captured run, including `--mutants` variants and imported helpers |
| `/decisions/:id` | ADRs navigable by context, options, decision, trade-offs, consequences and reversal conditions |
| `/glossary`, `/references` | Searchable, A–Z, linked back into chapters |
| Ctrl/⌘ K or `/` | Search across sections, terms, decisions, exercises and sources |

## Documentation

- [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md): what is in the handbook and how it maps to the UI
- [docs/DESIGN_SKILL_AUDIT.md](docs/DESIGN_SKILL_AUDIT.md): which design skills existed and how they were used
- [docs/REFERENCE_DESIGN_AUDIT.md](docs/REFERENCE_DESIGN_AUDIT.md): DataCamp and Google AI, inspected in a browser
- [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md): tokens, type, motion, accessibility
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md): stack, structure, decisions
- [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md): what was tested and what was found

The brief asked for the documents in `ui-application/docs`. That folder belongs to an earlier, separate app, so to leave it untouched they are here, alongside the application they describe.
