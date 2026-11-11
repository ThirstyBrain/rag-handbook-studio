# RAG Handbook Studio

A production-grade RAG architecture handbook (`handbook/`) and the interactive reading application that renders it (`app/`).

| Folder | What it is |
|---|---|
| [`handbook/`](handbook) | Canonical content: chapters, ADRs, diagrams, exercises, reference implementation. Read-only input for the app. |
| [`app/`](app) | React + Vite + TypeScript reader. Reads `../handbook` at build time via the `@handbook` alias. |

## Quick start

```bash
cd app
npm ci
npm run dev      # http://localhost:5180
npm run check    # typecheck + lint + tests + build
```

Node 20+ is required. Python 3.11+ is only needed to re-capture exercise output (`npm run exercises`).

## Deploy

The app is a static SPA (History API routing, so every path must fall back to `index.html`). The build must see the whole repo because it imports `../handbook`.

- **Netlify:** import the repo; `netlify.toml` at the root configures everything.
- **Vercel:** import the repo, set *Root Directory* to `app`, and keep "Include files outside the Root Directory" enabled. `app/vercel.json` does the rest.

## Known issues

- `npm test` has one failing test while `ch29_sql_guard.py` cannot run: it needs `psycopg`, and its captured run in `app/src/generated/exercise-runs.json` records a failure. Install `psycopg` and run `npm run exercises` to refresh.
- Large single chunk: the whole handbook ships in one cached chunk (see UI-ADR-1 in `app/docs/IMPLEMENTATION_PLAN.md`).

## Layout rule

Edit content in `handbook/`, never from `app/`. After changing exercises, run `npm run exercises` in `app/` to refresh captured output.
