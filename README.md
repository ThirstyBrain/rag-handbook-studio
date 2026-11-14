# RAG Architecture Handbook

**An evidence-labelled engineering handbook for designing, evaluating, securing and operating production Retrieval-Augmented Generation (RAG) systems, with an interactive reading application.**

[![CI](https://github.com/ThirstyBrain/rag-handbook-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/ThirstyBrain/rag-handbook-studio/actions/workflows/ci.yml)
[![Live site](https://img.shields.io/badge/live-rag--handbook--studio.netlify.app-0a7d5a)](https://rag-handbook-studio.netlify.app/)

**Read it online: [rag-handbook-studio.netlify.app](https://rag-handbook-studio.netlify.app/)**

---

## Overview

Most RAG material stops at a demo. This handbook covers what comes after: the trade-offs, failure modes, security model, evaluation and cost decisions of a system that has to run in production. It is written for software architects, solution architects, technical leads and platform engineers.

Two things make it different from a blog series:

- **Every claim is labelled by its evidence.** A tag on each significant statement says whether it rests on a reviewed source, was executed in this repository, is engineering reasoning, an assumption, or illustrative only. Nothing is presented as a measured result unless it was measured.
- **The examples run.** Exercises are plain-Python scripts whose real output is captured and shown beside the source, including mutation checks that prove the tests can fail.

## What is inside

| Area | Contents |
|---|---|
| **Chapters** | 33 chapters in parts, from fundamentals (embeddings, chunking, vector stores) through hybrid search, reranking, agentic RAG, evaluation, monitoring, security and governance, to enterprise architecture patterns and interview preparation. Some chapters are still being written and say so. |
| **Architecture decisions** | 19 ADRs recording the context, options considered, decision, trade-offs and the conditions that would reverse it. |
| **Exercises** | 29 runnable scripts with captured output and knowledge-checkpoint questions. |
| **Glossary and references** | 256 defined terms and 200+ reviewed sources, linked back to the chapters that use them. |
| **Diagrams** | 60+ Mermaid diagrams, rendered in the reader and as figures. |
| **Reference implementation** | A runnable, incrementally built backend (FastAPI, PostgreSQL with pgvector, an LLM gateway with provider fallback). Work in progress; see its README for current status. |

## The reading application

The reader renders the handbook's own Markdown, so the site and the repository never drift apart.

- Chapter reader with outline and scroll-spy, reading progress, evidence highlighter, source popovers, highlighted code with copy, and `[` / `]` to move between chapters
- Architecture map linking each pipeline stage to its chapters, diagrams and decisions
- A hybrid-search lab that runs BM25, a trigram stand-in for vectors and reciprocal rank fusion in the browser, with per-term score explanations
- Command palette search (`Ctrl/⌘ K` or `/`) across chapters, terms, decisions, exercises and sources
- Static prerendering of every route, so the content is available without JavaScript
- Built with React 18, TypeScript, Vite, Marked and Mermaid. Tested with Vitest and Testing Library.

## Repository layout

```
.
├── handbook/     Canonical content: chapters, ADRs, diagrams, exercises, reference implementation
├── app/          React + Vite reading application (reads ../handbook at build time)
├── netlify.toml  Deployment configuration
└── .github/      Continuous integration
```

The application treats `handbook/` as read-only input. Edit content there, never from `app/`.

## Getting started

Requires Node.js 20 or later. Python 3.11 or later is needed only to re-capture exercise output.

```bash
git clone https://github.com/ThirstyBrain/rag-handbook-studio.git
cd rag-handbook-studio/app
npm ci
npm run dev        # http://localhost:5180
```

| Command | Purpose |
|---|---|
| `npm run dev` | Development server |
| `npm run build` | Type-check, bundle, then prerender every route into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run check` | Type-check, lint, test and build |
| `npm run exercises` | Re-run the handbook exercises and record their output |
| `npm run dates` | Record chapter and ADR "last updated" dates after you edit the handbook (commit `app/content-dates.json`) |

## How it is built

The site is fully static. `npm run build` bundles the app, then `app/scripts/prerender.mjs` writes one HTML file per route with its own title, description, canonical link, Open Graph tags and JSON-LD (TechArticle, BreadcrumbList, FAQPage, DefinedTermSet). It also generates `sitemap.xml`, `robots.txt`, `llms.txt` and a `404.html`. Unknown URLs return a real 404. Each page also gets a generated 1200×630 social card in `dist/og/`. "Last updated" dates come from `app/content-dates.json`, recorded from real file timestamps and superseded by git history once a chapter's text changes, so a date never moves unless the content does.

Design notes and audits live in [`app/docs/`](app/docs): implementation plan, design system, and validation report.

## Deployment

Hosted on Netlify, deployed from `main`. [`netlify.toml`](netlify.toml) sets the base directory (`app`), build command and publish directory.

- **Netlify:** import the repository; no further settings are needed.
- **Vercel:** set the Root Directory to `app` and keep "Include files outside the Root Directory" enabled.

The canonical origin comes from `SITE_URL`, then Netlify's `URL` variable, then the default in `app/src/seo/siteConfig.ts`. Set `SITE_URL` if you move to a custom domain. Set `PLAUSIBLE_DOMAIN` to add privacy-friendly analytics; nothing is added by default.

The author byline and structured data come from `AUTHOR` in `app/src/seo/siteConfig.ts`; add `bio` and `sameAs` profile links (for example LinkedIn) there.

## Status and known issues

- The handbook is in active development; chapters marked in progress will change.
- One test (`ch29_sql_guard.py` captured run) fails on machines without the `psycopg` package. Install it and run `npm run exercises` to refresh the capture.
- The whole handbook ships as one cached JavaScript chunk. Splitting it per chapter is planned; see UI-ADR-1 in [`app/docs/IMPLEMENTATION_PLAN.md`](app/docs/IMPLEMENTATION_PLAN.md).

## Feedback and corrections

Found an error, a stale source or an exercise that does not run? [Open an issue](https://github.com/ThirstyBrain/rag-handbook-studio/issues) naming the chapter and section.

## Author

Created and maintained by [Kumar Shivam](https://github.com/ThirstyBrain).
