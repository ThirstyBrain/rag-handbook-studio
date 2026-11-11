# Reference implementation

A runnable, incrementally built reference implementation for the handbook (see `../project-management/M1-ARCHITECTURE-AND-ROADMAP.md` §6 for the 20-component roadmap and `../adr/` for decisions).

**Status:** components 1 (foundation), 2 (database schema, roles, migrations), 3 (document ingestion API, object storage, job queue and worker) 4 (extraction and chunking) and 5 (chunk embedding through the gateway) of 20, plus the cross-cutting **LLM gateway**, are built and verified. Nothing else exists yet: no vector indexes, retrieval or generation features, and embeddings have been verified only with the gateway's fake provider. See `../project-management/PROGRESS.md` for the live state.

## What exists

| Path | Contents |
|---|---|
| `backend/src/rag_service/core/` | Settings, structured JSON logging with credential scrubbing, problem+json errors, request middleware, events |
| `backend/src/rag_service/features/health/` | Liveness and readiness (feature-first: schemas, service, adapter, router) |
| `backend/src/rag_service/main.py` | App factory `create_app()` |
| `backend/src/rag_service/features/ingestion/` | Upload API (`POST/GET/DELETE /v1/documents`), content validation, raw object storage port + filesystem adapter, idempotent versioning |
| `backend/src/rag_service/jobs/` | Postgres-backed job queue (`SKIP LOCKED`, leases, retries, dead state), handlers, worker process |
| `backend/src/rag_service/security/identity.py` | **Development-only** identity from `X-Dev-*` headers until authentication (component 13) |
| `scripts/mutation_ingest.py` | Mutation check for ingestion, jobs, storage safety and the jobs migration |
| `backend/src/rag_service/features/extraction/` | Text extraction from untrusted files: parsers (text, Markdown, HTML, DOCX, PDF), the sandboxed child process and its limits |
| `backend/src/rag_service/features/chunking/` | Deterministic structure-aware chunker (sections, sentences, table headers, overlap) |
| `database/migrations/0003_extraction_chunks.sql` | The worker's narrow chunk-write path; binds the earlier policies to `rag_app` |
| `backend/src/rag_service/features/embedding/` | Chunk embedding through the gateway `embed` route (ADR-017); `database/migrations/0004_chunk_embeddings.sql` stores vectors. Needs the pgvector extension installed by an administrator, and a gateway config with an `embed` route (`RAG_EMBEDDING_ENABLED`, default on in the worker, off in the base compose stack) |
| `scripts/mutation_embed.py` | Mutation check for embedding, the vector write path and migration 0004 |
| `scripts/mutation_extract.py` | Mutation check for extraction, chunking, the sandbox, the worker's content path and migration 0003 |
| `backend/src/rag_service/db/` | Tenant-scoped data access (`Database.run(identity, work)`), identity model, migration runner |
| `database/migrations/` | Forward-only SQL migrations (`0001_core_schema.sql`: schema, row-level security, grants) |
| `database/init/` | First-start bootstrap: pgvector extension, `rag_owner` and `rag_app` roles |
| `scripts/mutation_db.py`, `scripts/pg_test_env.py` | Mutation check for the database layer; exports the database test variables from `.env` |
| `backend/src/rag_service/features/llm/` | **LLM gateway**: one provider-neutral way to call Claude, OpenAI, Grok or local models (Ollama, vLLM). **Start with its [README](backend/src/rag_service/features/llm/README.md).** |
| `config/llm-gateway.example.toml` | Example routes, providers and fallback chains (no secrets) |
| `docker-compose.llm.yml` | Optional override that enables the gateway in the API container |
| `scripts/mutation_llm.py` | Mutation check for the gateway's policy code |
| `tests/` | Unit tests and integration tests (the latter need PostgreSQL) |
| `docker/postgres/`, `database/init/` | PostgreSQL 16 + pgvector 0.8.7 image (built from source, digest-pinned base) |
| `docker-compose.yml` | Local stack: `db` and `api`, loopback-only ports, read-only API container, non-root, capabilities dropped |
| `scripts/check.py` | One-command lint + format + type + test gate |
| `DEPENDENCIES.md` | Pinned packages, versions, licenses, purpose |

## Run it

```bash
cd reference-implementation
cp .env.example .env            # then set POSTGRES_PASSWORD, RAG_OWNER_PASSWORD, RAG_APP_PASSWORD (URL-safe characters only)
docker compose up -d --build     # db -> migrate (one-shot, as rag_owner) -> api (as rag_app)
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready   # 200 when PostgreSQL is reachable, 503 otherwise
docker compose down            # add -v to delete the database volume
```

## Develop and test

```bash
cd reference-implementation/backend
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python ../scripts/check.py                            # ruff, ruff format --check, mypy --strict, pytest
# with the compose database running, include the integration tests:
#   export RAG_TEST_DATABASE_URL=postgresql://rag:<password>@127.0.0.1:5433/rag
```

## Try the ingestion API (local development only)

The upload endpoint needs an identity. Until authentication exists (component 13) a development-only header identity can be switched on: **never do this outside your own machine**; the service refuses it when `RAG_ENVIRONMENT=production`.

```bash
# in .env: RAG_ENVIRONMENT=local   RAG_DEV_IDENTITY_ENABLED=true     (then: docker compose up -d --build)
T=$(uuidgen)   # a tenant must exist: create it with the bootstrap role, e.g.
docker compose exec -T db psql -U rag -d rag -c "INSERT INTO rag.tenants (tenant_id, name) VALUES ('$T', 'demo')"
H=(-H "X-Dev-Tenant: $T" -H "X-Dev-User: alice" -H "X-Dev-Groups: eng")
curl -s "${H[@]}" -H "Content-Type: text/markdown" --data-binary @README.md \
     "http://127.0.0.1:8000/v1/documents?source_id=readme.md&title=Readme"      # 202: new version queued
curl -s "${H[@]}" "http://127.0.0.1:8000/v1/documents"                          # list
docker compose logs worker --no-log-prefix | tail -3                            # the worker extracted and chunked it
```

After the worker has run, the version is still `staged` but its chunks exist (activation happens once indexing exists, component 6). A file the worker cannot process (encrypted PDF, malformed or hostile Word file, a PDF with no text) leaves the version `failed` with a short reason code and the job `dead` after one attempt. Same content again returns `200` with `"duplicate": true`; new content creates version 2. The size limit (`RAG_MAX_UPLOAD_BYTES`, 25 MiB default), content-type check and ACL rules are described in `backend/src/rag_service/features/ingestion/`.

## Database tests

The tests that exercise the real schema create scratch databases, so they need the bootstrap superuser URL and the two role passwords. With the stack's `db` service running:

```bash
cd reference-implementation/backend
python ../scripts/pg_test_env.py | Invoke-Expression                        # PowerShell
eval "$(python ../scripts/pg_test_env.py --shell bash)"                      # bash/zsh
python ../scripts/check.py                                                   # all tests incl. database and local Ollama
python ../scripts/mutation_db.py                                             # inject defects, expect every one to be caught
```

Without these variables the database tests are skipped (and the skip reason is shown). Add a migration as the next numbered file in `database/migrations/`; never edit an applied one (the runner rejects it). New tenant-owned tables must follow the pattern in `0001_core_schema.sql` or a guard test fails.

## Using models

Features never import a vendor SDK; they call the gateway by route name. Copy `config/llm-gateway.example.toml`, set real model ids, export the API keys you have (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`) and point `RAG_LLM_CONFIG_FILE` at the file. Local models (Ollama) need no key. See the gateway README for routes, fallback order, data-sensitivity rules, streaming, embeddings and testing without a model.

## Configuration

All settings are environment variables prefixed `RAG_` (see `backend/src/rag_service/core/config.py`); secrets are never committed. `.env` is git-ignored.

## Known limitations (also in `../project-management/OPEN-ISSUES.md`)

- Database roles are created only when a database volume is first initialised. After pulling a change that adds a role (`rag_worker`), run `docker compose down -v` (this deletes local development data) or create the role by hand, and rebuild the database image with `docker compose up -d --build`.
- **There is no authentication yet** (OI-052): the development identity is for local use only. The worker cannot read chunk content by design; it has only a narrow write path to staged chunks (ADR-016). Raw files live on a shared local volume (the Azure Blob adapter is future work).
- Tenant provisioning is not an application operation yet (OI-051): tenants are created through a privileged path (tests use the bootstrap superuser).
- RLS with ACL overlap has not been performance-tested on realistic sizes (OI-051).
- The extraction child has no network or filesystem isolation of its own, and its POSIX resource limits have been written but not observed on the Windows development host (OI-053). Run extraction only inside the compose worker (read-only root, no capabilities, memory and pid limits) for untrusted files.
- Requirements are version-pinned but not hash-pinned.
- The PostgreSQL image is built from source because the official pgvector image could not be pulled on the dev machine (OI-036).
- The gateway has not been called against the live Claude, OpenAI or Grok APIs (no keys were available); OpenAI and Grok wire formats are unverified against vendor docs. Run `tests/integration/test_llm_live.py` with your key (see the file) to verify Claude.
- No local embedding model is installed in the dev environment (all installed Ollama models are chat models).
- No authentication yet (component 13); the health endpoints are unauthenticated by design.
