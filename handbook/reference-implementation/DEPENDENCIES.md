# Dependencies (backend)

Versions are exact pins in `backend/requirements.txt` (runtime) and `backend/requirements-dev.txt` (tooling), resolved with pip on 2026-11-08. Licenses are the package metadata `License-Expression`/classifier as installed (not independently audited). Known limitation: pins are versions only, not hashes (`--require-hashes` is a hardening step for CI, component 20).

## Runtime

| Package | Version | License | Purpose | Notes / security |
|---|---|---|---|---|
| fastapi | 0.162.2 | MIT | HTTP API framework | Requires Python ≥ 3.10, pydantic ≥ 2.9 (SRC-013) |
| starlette | 1.10.0 | BSD-3-Clause | ASGI toolkit used by FastAPI | Pure-ASGI middleware used for streaming safety |
| pydantic / pydantic-core | 2.14.3 / 2.50.4 | MIT | Validation and settings models | |
| pydantic-settings | 2.16.2 | MIT | Environment-based configuration | `SecretStr` for secrets |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server | Run with `--no-access-log --no-server-header` |
| psycopg / psycopg-binary | 3.3.8 | **LGPL-3.0-only** | PostgreSQL driver | LGPL: used unmodified as a dynamically installed library; legal review recommended before redistributing images (CLAUDE.md 9.6) |
| psycopg-pool | 3.3.3 | **LGPL-3.0-only** | Connection pool for the tenant-scoped access layer | Same family and licence note as psycopg; open/close lifecycle managed by the app |
| opentelemetry-api | 1.45.2 | Apache-2.0 | Pulled in by FastAPI; API only (SDK and exporters arrive with component 16) | |
| httpx / httpcore / certifi | 0.28.1 / 1.0.9 / 2026.10.23 | BSD-3-Clause / BSD-3-Clause / **MPL-2.0** | HTTP client for the OpenAI-compatible LLM adapter (OpenAI, Grok, Ollama, vLLM) | Promoted from dev-only to runtime |
| anthropic | 2.6.0 | Apache-2.0 | Official Claude SDK used by the `anthropic` adapter; imported lazily, so the service runs without it if no Claude provider is configured | Built on `httpx2` (not `httpx`); sends the API key as a bearer token and `anthropic-version: 2026-10-21` (observed); retries disabled by the gateway |
| httpx2 / httpcore2 | 2.16.0 | BSD-3-Clause | HTTP stack used by the Claude SDK | A second HTTP client stack alongside httpx; accepted trade-off |
| jiter, docstring-parser, sniffio, truststore | 0.19.0, 0.18.0, 1.3.1, 0.10.5 | MIT, MIT, MIT OR Apache-2.0, MIT | Transitive dependencies of the Claude SDK | |
| pypdf | 7.0.0 | BSD-3-Clause | PDF text extraction, run only inside the sandboxed extraction child (ADR-016) | No required dependencies on Python ≥ 3.11 (PyPI metadata, SRC-125). No OCR, no table or heading recovery. Its maintainers state callers must catch its exceptions; the optional `crypto`, `image` and `full` extras are NOT installed, so encrypted PDFs are rejected |
| anyio, click, h11, idna, typing-extensions, typing-inspection, annotated-types, annotated-doc, python-dotenv | see requirements.txt | MIT / BSD / PSF | Transitive | |
| colorama, tzdata (Windows only) | 0.4.6, 2026.6 | BSD, Apache-2.0 | Transitive on Windows hosts | Not installed in the Linux image |

## Development / test

| Package | Version | License | Purpose |
|---|---|---|---|
| pytest, pytest-asyncio | 9.2.0, 1.4.1.post1 | MIT, Apache-2.0 | Tests |
| httpx | (runtime, see above) | | Also used as the in-process ASGI test client |
| ruff | 0.17.4 | MIT | Lint and format |
| mypy (+ mypy-extensions, librt, ast-serialize, pathspec) | 2.4.1 | MIT (pathspec: **MPL-2.0**) | Static types (strict) |

## Adding or changing a dependency

Add it to `requirements.txt` (runtime) or `requirements-dev.txt` with an exact pin, record purpose and license here, rebuild the image (`docker compose build api`), and run `python ../scripts/check.py`. Prefer standard-library solutions: the gateway configuration uses `tomllib`, not a TOML package.

## Compatibility evidence

All pins (including `anthropic` 2.6.0 and its `httpx2` stack) install and the test suite passes on the Windows dev host with **Python 3.14.2**, and the runtime pins install in `python:3.13-slim` (Linux) where the API container runs. This partly resolves OI-008. The container image is built from a digest-pinned base (see `backend/Dockerfile`).
