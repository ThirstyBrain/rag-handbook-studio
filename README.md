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

The app is a static site. `npm run build` type-checks, bundles, then **prerenders every route to static HTML** (`app/scripts/prerender.mjs`) so crawlers and AI tools get real content without running JavaScript. It also writes `404.html`, `sitemap.xml`, `robots.txt` and `llms.txt`. There is deliberately no catch-all rewrite: unknown URLs return a true 404. The build must see the whole repo because it imports `../handbook`.

- **Netlify:** import the repo; `netlify.toml` at the root configures everything.
- **Vercel:** import the repo, set *Root Directory* to `app`, and keep "Include files outside the Root Directory" enabled.

The canonical site origin is `SITE_URL`, else Netlify's `URL` variable, else `DEFAULT_SITE_URL` in `app/src/seo/siteConfig.ts`. Set `SITE_URL` when you add a custom domain.

## SEO and AEO

All of it lives in `app/src/seo`: per-page titles, descriptions, canonicals, Open Graph/Twitter tags and JSON-LD (TechArticle, BreadcrumbList, FAQPage from each chapter's interview questions, DefinedTermSet for the glossary). "Last updated" dates come from git history. To get a social preview image, add a 1200x630 `app/public/og-image.png`; the build picks it up automatically.

## Known issues

- `npm test` has one failing test while `ch29_sql_guard.py` cannot run: it needs `psycopg`, and its captured run in `app/src/generated/exercise-runs.json` records a failure. Install `psycopg` and run `npm run exercises` to refresh.
- Large single chunk: the whole handbook ships in one cached chunk (see UI-ADR-1 in `app/docs/IMPLEMENTATION_PLAN.md`).

## Layout rule

Edit content in `handbook/`, never from `app/`. After changing exercises, run `npm run exercises` in `app/` to refresh captured output.
