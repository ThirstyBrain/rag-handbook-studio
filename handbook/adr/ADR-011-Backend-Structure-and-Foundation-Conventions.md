# ADR-011: Backend Structure and Foundation Conventions

## Status

Accepted — 2026-11-08 (implemented and verified for component 1; conventions apply to all later components).

## Context

The reference implementation needs a structure that keeps business logic independent of HTTP and drivers, makes failure behaviour uniform, and avoids leaking secrets through logs and error bodies. Owner constraints: feature-first structure, clean architecture, no god classes, no hard-coded values, minimal packages, logging/error/analytics/tests in every feature.

## Requirements

Uniform error shape; correlation across logs; no secrets in logs or responses; testable without infrastructure; streaming-safe middleware (generation endpoints stream later); probes that fail closed; runs on the Windows dev host and in Linux containers.

## Options Considered

- **Structure:** A) layered by technical role (`routers/`, `services/`, `models/`), B) feature-first with a thin shared `core/` (chosen).
- **Middleware:** A) Starlette `BaseHTTPMiddleware`, B) pure ASGI middleware (chosen).
- **Database access for probes:** A) async psycopg, B) sync psycopg in a worker thread (chosen for the probe).
- **Errors:** A) ad-hoc JSON, B) RFC 9457 problem details (chosen).

## Decision

1. **Feature-first** packages under `rag_service/features/<feature>/` (schemas, service, adapters, router); `core/` holds only cross-cutting infrastructure. Services depend on `Protocol` ports; adapters (for example the PostgreSQL probe) implement them; `create_app()` wires them (dependency injection, no globals).
2. **Configuration** only through `Settings` (`RAG_`-prefixed environment, `SecretStr` for secrets); nothing tunable is hard-coded elsewhere. API docs are off by default and never in production.
3. **Errors** are RFC 9457 `application/problem+json` [RFC 9457: `type` may be a non-resolvable URI, extension members are allowed, stack dumps should not be exposed]; deliberate errors use `AppError(code, title, status)`; validation errors report location and rule, never the offending value; unhandled exceptions become a generic 500 with a request id.
4. **Logging** is structured JSON with request correlation; sensitive keys are masked and credentials inside free text or exception messages (URL userinfo, `password=`) are scrubbed; request logs contain method, path, status and duration only (no query string, headers or bodies).
5. **Middleware** is pure ASGI; inbound request ids are accepted only when they match a safe pattern; security headers are added to every response.
6. **Analytics events** are emitted through an `EventSink` port (default: structured log line) with scalar properties only.
7. **Readiness** runs dependency checks concurrently, each with a timeout, returns 503 on any failure, and never exposes exception text; liveness never touches dependencies.
8. **Database probes** use synchronous psycopg in a worker thread because psycopg's async API cannot run on Windows' default ProactorEventLoop. The data-access layer (component 2) must decide explicitly between sync-in-threadpool and async with a selector loop, and test on the dev host and in the container.
9. **Containers** run as a non-root user with a read-only root filesystem, dropped capabilities, resource limits and loopback-only published ports; base images are digest-pinned.
10. **Quality gate:** ruff (lint and format), mypy strict, pytest; `scripts/check.py` is the single command used locally and by CI.

## Rationale

These choices follow from executed evidence: the unhandled-exception test exposed that exception text in logs could contain a DSN, which led to the scrubber; pure ASGI middleware was chosen because the generation endpoints will stream; the Windows event-loop constraint is a documented psycopg limitation hit by the dev host.

## Trade-offs

More files and indirection than a single `main.py`; thread offload per probe; scrubbing is pattern-based and cannot catch every secret format; strict mypy and ruff add friction.

## Consequences

Every later feature follows the same package shape, error model, logging rules and test layout; each adds its own readiness check if it owns a dependency.

## Security Considerations

No secrets in code, logs or responses; request ids sanitised; docs endpoints disabled in production; non-root read-only container; probes do not disclose versions, hosts or errors. Residual risks: regex scrubbing is best-effort; the foundation stack still uses the bootstrap database superuser (removed in component 2); no authentication yet.

## Performance and Cost

The probe adds one connection per readiness request (about 30–55 ms measured locally, **[X]** informal single samples, not a benchmark). No other measurements.

## Reversal Conditions

Switch the probe to async when the data layer standardises on async psycopg with a selector loop; adopt a middleware framework if requirements outgrow pure ASGI; replace regex scrubbing with allow-listed logging fields if a leak is ever found.

## References

SRC-013 (FastAPI), RFC 9457 (read 2026-11-08), PostgreSQL/pgvector ADR-001 sources. Package versions: `reference-implementation/DEPENDENCIES.md`.

## Update 2026-11-09

Item 8 (database access) is superseded by ADR-013: the data layer uses synchronous psycopg with a connection pool in worker threads, with transaction-scoped identity. The readiness probes keep their own short-lived connections.
