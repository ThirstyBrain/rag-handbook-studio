"""Mutation check for ingestion, the job queue, content/storage safety and the jobs migration.

Each mutant applies one realistic defect, runs the ingestion/jobs/security tests, expects a FAILURE
(mutant killed), and always restores the original file. Needs the compose database and the RAG_TEST_*
variables (python scripts/pg_test_env.py). Run from reference-implementation/backend:
    python ../scripts/mutation_ingest.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SRC = BACKEND / "src" / "rag_service"
MIG = ROOT / "database" / "migrations" / "0002_ingestion_jobs.sql"
SVC = SRC / "features" / "ingestion" / "service.py"
MEDIA = SRC / "features" / "ingestion" / "media.py"
STORE = SRC / "features" / "ingestion" / "storage.py"
HANDLERS = SRC / "jobs" / "handlers.py"
QUEUE = SRC / "jobs" / "queue.py"
WORKER = SRC / "jobs" / "worker.py"
TESTS = [
    "../tests/unit/test_ingestion_units.py",
    "../tests/integration/test_ingestion_api.py",
    "../tests/integration/test_jobs.py",
    "../tests/integration/test_schema_security.py",
]

# (file, original, mutated, description)
MUTANTS: list[tuple[Path, str | tuple[str, ...], str | tuple[str, ...], str]] = [
    (
        SVC,
        "if not set(acl) <= set(identity.groups):",
        "if False:",
        "ACL may name groups the caller is not in",
    ),
    (SVC, "if size > self._max:", "if False:", "size limit not enforced on the stream"),
    (SVC, "if media_type is None:", "if False:", "disallowed content types accepted"),
    (
        SVC,
        'AND source_id = %s FOR UPDATE"',
        'AND source_id = %s"',
        "concurrent writers of one document not serialised",
    ),
    (
        SVC,
        "if visible is not None:\n                    raise _Replan",
        "if False:\n                    raise _Replan",
        "document-creation race returns a spurious conflict",
    ),
    (SVC, "if plan.is_new:", "if False:", "orphan object left after a failed upload"),
    (
        SVC,
        "document id that is not the live one: remove it.\n                    await asyncio.to_thread(self._store.delete, key)\n",
        "document id that is not the live one: remove it.\n",
        "orphan object left after a re-plan",
    ),
    (
        SVC,
        "AND document_id = %s AND state = 'staged'",
        "AND document_id = %s AND state = 'never'",
        "older staged versions not superseded (reverts blocked)",
    ),
    (
        SVC,
        "AND version > %s AND state = 'staged'",
        "AND version > %s AND state = 'never'",
        "newer staged versions not abandoned on revert-to-active",
    ),
    (MEDIA, "or b == 0x7F", "or False", "control characters accepted as text"),
    (
        MEDIA,
        "return DOCX if declared_type == DOCX else None",
        "return DOCX",
        "any zip accepted as a Word document",
    ),
    (
        STORE,
        "if digest.hexdigest() != sha256:",
        "if False:",
        "stored content not verified against its hash",
    ),
    (
        STORE,
        ('[0-9a-f]{64}$"', "_KEY.fullmatch(key)"),
        ('[0-9a-f]{64}"', "_KEY.match(key)"),
        # the end anchor and fullmatch overlap: removing only one is an equivalent mutant
        "object key may carry a trailing path (anchor and fullmatch removed)",
    ),
    (
        HANDLERS,
        "if not key.startswith(tenant_prefix(job.tenant_id)):",
        "if False:",
        "ingest handler accepts another tenant's key",
    ),
    (
        HANDLERS,
        "if store.sha256(key) != expected:",
        "if False:",
        "tampered objects pass verification",
    ),
    (
        HANDLERS,
        "if not key.startswith(\n                prefix",
        "if False and not key.startswith(\n                prefix",
        "delete handler accepts another tenant's key",
    ),
    (
        QUEUE,
        "OR (state = 'running' AND lease_expires_at < now())",
        "OR (state = 'running' AND false)",
        "crashed workers' jobs never reclaimed",
    ),
    (
        QUEUE,
        "if job.attempts > job.max_attempts:",
        "if False:",
        "jobs retried beyond max attempts after lease expiry",
    ),
    (
        QUEUE,
        "\"WHERE job_id = %s AND state = 'running' AND locked_by = %s\",\n                (job.job_id, worker),",
        "\"WHERE job_id = %s AND state = 'running' AND %s IS NOT NULL\",\n                (job.job_id, worker),",
        "a worker that lost its lease can complete the job",
    ),
    (
        QUEUE,
        "CASE WHEN attempts >= max_attempts THEN 'dead'",
        "CASE WHEN attempts > max_attempts THEN 'dead'",
        "jobs get one attempt too many",
    ),
    (
        WORKER,
        "float(min(self._cap, self._base * 2.0 ** (attempts - 1)))",
        "0.0",
        "no backoff between retries",
    ),
    (
        MIG,
        "CREATE POLICY jobs_app_insert ON rag.ingestion_jobs FOR INSERT TO rag_app\n  WITH CHECK (tenant_id = rag.app_tenant());",
        "CREATE POLICY jobs_app_insert ON rag.ingestion_jobs FOR INSERT TO rag_app\n  WITH CHECK (true);",
        "API can enqueue jobs for other tenants",
    ),
    (
        MIG,
        "CREATE POLICY jobs_app_select ON rag.ingestion_jobs FOR SELECT TO rag_app\n  USING (tenant_id = rag.app_tenant());",
        "CREATE POLICY jobs_app_select ON rag.ingestion_jobs FOR SELECT TO rag_app\n  USING (true);",
        "API can read other tenants' jobs",
    ),
    (
        MIG,
        "GRANT SELECT, INSERT ON rag.ingestion_jobs TO rag_app;",
        "GRANT SELECT, INSERT, UPDATE ON rag.ingestion_jobs TO rag_app;",
        "API granted UPDATE on jobs",
    ),
    (
        MIG,
        "GRANT SELECT, UPDATE ON rag.ingestion_jobs TO rag_worker;",
        "GRANT SELECT, UPDATE, INSERT, DELETE ON rag.ingestion_jobs TO rag_worker;",
        "worker over-granted on jobs",
    ),
    (
        MIG,
        "GRANT SELECT, UPDATE ON rag.ingestion_jobs TO rag_worker;",
        "GRANT SELECT, UPDATE ON rag.ingestion_jobs TO rag_worker;\nGRANT SELECT ON rag.chunks TO rag_worker;",
        "worker can read content tables",
    ),
    (
        MIG,
        "ALTER TABLE rag.ingestion_jobs FORCE  ROW LEVEL SECURITY;",
        "SELECT 1;",
        "jobs: FORCE RLS removed",
    ),
    (
        SRC / "security" / "identity.py",
        "if settings.is_production or not settings.dev_identity_enabled:",
        "if not settings.dev_identity_enabled:",
        "dev identity accepted in production",
    ),
    (
        SRC / "core" / "config.py",
        'if self.dev_identity_enabled and self.environment == "production":',
        "if False:",
        "settings accept dev identity in production",
    ),
]


def run_tests() -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-c", "pyproject.toml", *TESTS]
    result = subprocess.run(cmd, cwd=BACKEND, capture_output=True, check=False, env=os.environ)  # noqa: S603 - fixed argument list
    return result.returncode == 0


def main() -> int:
    needed = (
        "RAG_TEST_ADMIN_URL",
        "RAG_TEST_OWNER_PASSWORD",
        "RAG_TEST_APP_PASSWORD",
        "RAG_TEST_WORKER_PASSWORD",
    )
    if not all(k in os.environ for k in needed):
        print("set the RAG_TEST_* variables first (python scripts/pg_test_env.py)")
        return 2
    if not run_tests():
        print("baseline tests fail: fix them before mutation testing")
        return 2
    only = (
        sys.argv[1] if len(sys.argv) > 1 else None
    )  # optional: run only mutants whose description contains this
    survived: list[str] = []
    ran = 0
    for path, original, mutated, description in MUTANTS:
        if only and only not in description:
            continue
        ran += 1
        pairs = (
            list(zip(original, mutated, strict=True))
            if isinstance(original, tuple)
            else [(original, mutated)]
        )
        count = -1 if isinstance(original, tuple) else 1
        source = path.read_text(encoding="utf-8")
        if any(o not in source for o, _ in pairs):  # type: ignore[operator]
            print(f"PATTERN MISSING: {description}", flush=True)
            survived.append(f"pattern missing: {description}")
            continue
        mutated_source = source
        for o, m in pairs:
            mutated_source = mutated_source.replace(o, m, count)  # type: ignore[arg-type]
        try:
            path.write_text(mutated_source, encoding="utf-8")
            killed = not run_tests()
        finally:
            path.write_text(source, encoding="utf-8")
        print(
            f"{'killed  ' if killed else 'SURVIVED'}  {path.name}: {description}",
            flush=True,
        )
        if not killed:
            survived.append(description)
    print(f"\n{ran - len(survived)}/{ran} mutants killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
