"""Mutation check for the database layer: schema/RLS migration, identity, pooled transactions, runner.

Each mutant applies one realistic defect, runs the database tests, expects a FAILURE (mutant killed), and
always restores the original file. Needs the compose database and the RAG_TEST_* variables
(see reference-implementation/README.md, "Database tests"). Run from reference-implementation/backend:
    python ../scripts/mutation_db.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
MIGRATION = ROOT / "database" / "migrations" / "0001_core_schema.sql"
DB_PKG = BACKEND / "src" / "rag_service" / "db"
TESTS = [
    "../tests/unit/test_db_files.py",
    "../tests/integration/test_migrations.py",
    "../tests/integration/test_schema_security.py",
]

M = MIGRATION
# (file, original, mutated, description)
MUTANTS: list[tuple[Path, str, str, str]] = [
    (
        M,
        "ALTER TABLE rag.chunks            FORCE  ROW LEVEL SECURITY;",
        "SELECT 1;",
        "chunks: FORCE RLS removed (owner bypasses)",
    ),
    (
        M,
        "ALTER TABLE rag.documents         ENABLE ROW LEVEL SECURITY;",
        "SELECT 1;",
        "documents: RLS not enabled",
    ),
    (
        M,
        "CREATE POLICY chunks_select ON rag.chunks FOR SELECT\n  USING (tenant_id = rag.app_tenant() AND acl_groups",
        "CREATE POLICY chunks_select ON rag.chunks FOR SELECT\n  USING (true AND acl_groups",
        "chunks SELECT: tenant check removed",
    ),
    (
        M,
        "CREATE POLICY chunks_select ON rag.chunks FOR SELECT\n  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups());",
        "CREATE POLICY chunks_select ON rag.chunks FOR SELECT\n  USING (tenant_id = rag.app_tenant());",
        "chunks SELECT: ACL check removed",
    ),
    (
        M,
        "CREATE POLICY chunks_insert ON rag.chunks FOR INSERT\n  WITH CHECK (tenant_id = rag.app_tenant());",
        "CREATE POLICY chunks_insert ON rag.chunks FOR INSERT\n  WITH CHECK (true);",
        "chunks INSERT: WITH CHECK removed (cross-tenant writes)",
    ),
    (
        M,
        "CREATE POLICY documents_update ON rag.documents FOR UPDATE\n  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups())\n  WITH CHECK (tenant_id = rag.app_tenant());",
        "CREATE POLICY documents_update ON rag.documents FOR UPDATE\n  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups())\n  WITH CHECK (true);",
        "documents UPDATE: WITH CHECK removed (move rows to another tenant)",
    ),
    (
        M,
        "AS $$ SELECT current_setting('app.tenant_id')::uuid $$;",
        "AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;",
        "missing identity returns no rows instead of failing closed",
    ),
    (
        M,
        "CREATE POLICY versions_select ON rag.document_versions FOR SELECT\n  USING (tenant_id = rag.app_tenant() AND EXISTS (",
        "CREATE POLICY versions_select ON rag.document_versions FOR SELECT\n  USING (tenant_id = rag.app_tenant() AND NOT EXISTS (",
        "versions no longer inherit document visibility",
    ),
    (
        M,
        "REFERENCES rag.document_versions ON DELETE CASCADE",
        "REFERENCES rag.document_versions",
        "chunks no longer cascade with their version",
    ),
    (
        M,
        "WHERE state IN ('staged', 'active');",
        "WHERE true;",
        "unique content hash no longer partial (reverts blocked)",
    ),
    (
        M,
        "GRANT SELECT, INSERT, UPDATE, DELETE ON rag.documents, rag.document_versions, rag.chunks TO rag_app;",
        "GRANT ALL ON rag.documents, rag.document_versions, rag.chunks TO rag_app;",
        "app role over-granted (TRUNCATE bypasses RLS)",
    ),
    (
        DB_PKG / "database.py",
        "set_config('app.tenant_id', %s, true)",
        "set_config('app.tenant_id', %s, false)",
        "identity set at session scope (leaks across pooled requests)",
    ),
    (
        DB_PKG / "identity.py",
        'r"^[A-Za-z0-9._:@/-]{1,128}$"',
        'r"^[^\\n]{1,128}$"',
        "identity values not restricted to a safe alphabet",
    ),
    (
        DB_PKG / "migrate.py",
        "if local.checksum != checksum:",
        "if False:",
        "edited migrations are not detected",
    ),
    (
        DB_PKG / "migrate.py",
        "if migration.version <= highest:",
        "if False:",
        "already-applied migrations are re-run",
    ),
]


def run_tests() -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-c", "pyproject.toml", *TESTS]
    result = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        cmd, cwd=BACKEND, capture_output=True, check=False, env=os.environ
    )
    return result.returncode == 0


def main() -> int:
    if not all(
        k in os.environ
        for k in (
            "RAG_TEST_ADMIN_URL",
            "RAG_TEST_OWNER_PASSWORD",
            "RAG_TEST_APP_PASSWORD",
            "RAG_TEST_WORKER_PASSWORD",
        )
    ):
        print(
            "set RAG_TEST_ADMIN_URL and the RAG_TEST_*_PASSWORD variables first (python scripts/pg_test_env.py)"
        )
        return 2
    if not run_tests():
        print("baseline tests fail: fix them before mutation testing")
        return 2
    survived: list[str] = []
    for path, original, mutated, description in MUTANTS:
        source = path.read_text(encoding="utf-8")
        if original not in source:
            print(f"PATTERN MISSING: {description}")
            survived.append(f"pattern missing: {description}")
            continue
        try:
            path.write_text(source.replace(original, mutated, 1), encoding="utf-8")
            killed = not run_tests()
        finally:
            path.write_text(source, encoding="utf-8")
        print(f"{'killed  ' if killed else 'SURVIVED'}  {path.name}: {description}")
        if not killed:
            survived.append(description)
    print(f"\n{len(MUTANTS) - len(survived)}/{len(MUTANTS)} mutants killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
