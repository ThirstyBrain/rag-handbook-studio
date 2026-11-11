"""Mutation check for extraction, chunking, the sandbox, the worker's content path and migration 0003.

Each mutant applies one realistic defect, runs the relevant tests, expects a FAILURE (mutant killed), and
always restores the original file. Unit-level code is checked against the unit tests only (they are meant
to catch it on their own); database-facing code against the integration tests. Needs the compose database
and the RAG_TEST_* variables (python scripts/pg_test_env.py). Run from reference-implementation/backend:
    python ../scripts/mutation_extract.py [description-filter]
A pattern that no longer matches the source is reported as a failure, so the script cannot rot silently.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FEATURES = BACKEND / "src" / "rag_service" / "features"
JOBS = BACKEND / "src" / "rag_service" / "jobs"
MIG = ROOT / "database" / "migrations" / "0003_extraction_chunks.sql"
CHUNKER = FEATURES / "chunking" / "chunker.py"
DOCX = FEATURES / "extraction" / "docx.py"
PDF = FEATURES / "extraction" / "pdf.py"
TEXTUAL = FEATURES / "extraction" / "textual.py"
MODEL = FEATURES / "extraction" / "model.py"
DISPATCH = FEATURES / "extraction" / "dispatch.py"
SANDBOX = FEATURES / "extraction" / "sandbox.py"
STORE = FEATURES / "ingestion" / "chunk_store.py"
PIPELINE = FEATURES / "ingestion" / "pipeline.py"

UNIT = [
    "../tests/unit/test_extraction.py",
    "../tests/unit/test_extraction_sandbox.py",
    "../tests/unit/test_chunker.py",
]
DB = [
    "../tests/integration/test_chunk_pipeline.py",
    "../tests/integration/test_jobs.py",
    "../tests/integration/test_schema_security.py",
]
RUN_TIMEOUT_S = 420  # a hanging mutant counts as killed (tests that never finish do not pass)

# (file, original, mutated, description, tests)
Mutant = tuple[Path, str | tuple[str, ...], str | tuple[str, ...], str, list[str]]
MUTANTS: list[Mutant] = [
    # ---------------------------------------------------------------- chunker
    (
        CHUNKER,
        "if new_units and tokens([*current, unit]) > config.target_tokens:",
        "if False:",
        "chunks never split at the target size",
        UNIT,
    ),
    (
        CHUNKER,
        "while current and tokens([*current, unit]) > config.target_tokens:",
        "while False:",
        "overlap may push a chunk over the cap",
        UNIT,
    ),
    (
        CHUNKER,
        'if block.kind == "heading":\n            flush()',
        'if block.kind == "heading":\n            pass',
        "a heading does not end the previous chunk",
        UNIT,
    ),
    (
        CHUNKER,
        "if total + unit.tokens > config.overlap_tokens:",
        "if False:",
        "overlap budget ignored",
        UNIT,
    ),
    (
        CHUNKER,
        "if first.header is not None and not first.is_header:",
        "if False:",
        "table header not repeated",
        UNIT,
    ),
    (
        CHUNKER,
        "is_header=(i == 0 and j == 0)",
        "is_header=False",
        "header row duplicated",
        UNIT,
    ),
    (
        CHUNKER,
        "if len(text) <= cap:",
        "if len(text) <= cap * 3:",
        "oversized units not split",
        UNIT,
    ),
    (
        CHUNKER,
        "_SENTENCE.split(block.text)",
        "[block.text]",
        "sentence boundaries ignored",
        UNIT,
    ),
    (
        CHUNKER,
        "min(pages) if pages else None",
        "max(pages) if pages else None",
        "page start wrong",
        UNIT,
    ),
    (
        CHUNKER,
        "if len(chunks) > config.max_chunks:",
        "if False:",
        "chunk count not limited",
        UNIT,
    ),
    (
        CHUNKER,
        "if not 0 <= self.overlap_tokens < self.target_tokens <= self.max_tokens:",
        "if False:",
        "chunk configuration not validated",
        UNIT,
    ),
    (
        CHUNKER,
        "while stack and stack[-1][0] >= level:",
        "while stack and stack[-1][0] > level:",
        "sibling headings nest under each other",
        UNIT,
    ),
    # ---------------------------------------------------------------- parsers and hygiene
    (
        DOCX,
        "or _DOCTYPE.search(xml)",
        "or False",
        "DOCTYPE and entities accepted in docx XML",
        UNIT,
    ),
    (
        DOCX,
        "if len(infos) > limits.max_zip_members:",
        "if False:",
        "zip member count unlimited",
        UNIT,
    ),
    (
        DOCX,
        "if sum(i.file_size for i in infos) > limits.max_uncompressed_bytes:",
        "if False:",
        "zip total size unlimited",
        UNIT,
    ),
    (
        DOCX,
        "> limits.max_compression_ratio",
        "> limits.max_compression_ratio * 1e9",
        "zip compression ratio unlimited",
        UNIT,
    ),
    (
        DOCX,
        "if info.flag_bits & 0x1:",
        "if False:",
        "encrypted zip members accepted",
        UNIT,
    ),
    (
        DOCX,
        "if depth > limits.max_xml_depth:",
        "if False:",
        "xml depth unlimited",
        UNIT,
    ),
    (
        DOCX,
        'elif tag == f"{_W}vanish":',
        "elif False:",
        "hidden docx text extracted",
        UNIT,
    ),
    (PDF, "if reader.is_encrypted:", "if False:", "encrypted pdf opened", UNIT),
    (
        PDF,
        "if page_count > limits.max_pages:",
        "if False:",
        "pdf page count unlimited",
        UNIT,
    ),
    (
        MODEL,
        'text = _SURROGATES.sub("\\ufffd", text)',
        "pass",
        "lone surrogates kept",
        UNIT,
    ),
    (
        MODEL,
        'unicodedata.normalize("NFC", _STRIP.sub("", text))',
        "text",
        "control characters kept",
        UNIT,
    ),
    (TEXTUAL, '"script",', "", "script content extracted from html", UNIT),
    (
        TEXTUAL,
        "if self._depth > _MAX_DEPTH:",
        "if False:",
        "html nesting unlimited",
        UNIT,
    ),
    (
        DISPATCH,
        "if len(data) > limits.max_input_bytes:",
        "if False:",
        "input size unlimited",
        UNIT,
    ),
    # ---------------------------------------------------------------- sandbox
    (
        SANDBOX,
        'raise Rejected("timeout") from None',
        'raise Rejected("extractor_crashed") from None',
        "timeout not reported as such",
        UNIT,
    ),
    (SANDBOX, "if len(out) > output_cap:", "if False:", "child output unbounded", UNIT),
    (
        SANDBOX,
        'env = {"PYTHONPATH": self._paths,',
        'env = {**os.environ, "PYTHONPATH": self._paths,',
        "child inherits the worker's environment (secrets)",
        UNIT,
    ),
    (
        SANDBOX,
        "cwd=scratch,",
        "cwd=None,",
        "child runs in the worker's working directory",
        UNIT,
    ),
    (
        SANDBOX,
        "or not 0 <= level <= 6",
        "or False",
        "child answer: heading level not validated",
        UNIT,
    ),
    (
        SANDBOX,
        "kind not in BLOCK_KINDS",
        "False",
        "child answer: block kind not validated",
        UNIT,
    ),
    (
        SANDBOX,
        "text = clean_text(\n            text\n        )  # again here",
        "text = text  # again here",
        "child answer not sanitised",
        UNIT,
    ),
    (
        SANDBOX,
        'raise Rejected(reason if ok else "extractor_error")',
        "raise Rejected(str(reason))",
        "child-supplied failure reason trusted",
        UNIT,
    ),
    # ---------------------------------------------------------------- worker content path
    (
        STORE,
        "AND v.version = %s AND v.state = 'staged'",
        "AND v.version = %s",
        "chunks written for non-staged versions",
        DB,
    ),
    (STORE, "AND d.status = 'active' ", "", "chunks written for deleted documents", DB),
    (
        STORE,
        'acl = list(row["acl_groups"])',
        'acl = ["public"]',
        "chunks do not inherit the ACL",
        DB,
    ),
    (
        STORE,
        '"DELETE FROM rag.chunks WHERE tenant_id = %s AND document_id = %s AND version = %s",',
        '"DELETE FROM rag.chunks WHERE tenant_id = %s AND document_id = %s AND version = %s AND false",',
        "re-chunking does not replace old chunks",
        DB,
    ),
    (
        STORE,
        "SET state = 'failed', failure_reason = %s",
        "SET failure_reason = %s",
        "failure not recorded",
        DB,
    ),
    (
        PIPELINE,
        "            self._chunks.mark_failed(",
        "            _ = (",
        "rejected files not marked failed",
        DB,
    ),
    (
        PIPELINE,
        "raise PermanentFailure(exc.reason) from None",
        "raise",
        "permanent failures retried",
        DB,
    ),
    (
        PIPELINE,
        "            if not chunks:\n                raise Rejected",
        "            if False:\n                raise Rejected",
        "empty chunk set accepted",
        DB,
    ),
    (
        JOBS / "queue.py",
        "(permanent, backoff_s,",
        "(False, backoff_s,",
        "permanent flag ignored by the queue",
        DB,
    ),
    (
        JOBS / "worker.py",
        "permanent = isinstance(exc, PermanentFailure)",
        "permanent = False",
        "runner never ends jobs permanently",
        DB,
    ),
    # ---------------------------------------------------------------- migration 0003
    (
        MIG,
        "ALTER POLICY chunks_insert    ON rag.chunks            TO rag_app;",
        "SELECT 1;",
        "app insert policy applies to PUBLIC again",
        DB,
    ),
    (
        MIG,
        "WITH CHECK (tenant_id = rag.app_tenant() AND state IN ('staged', 'failed'));",
        "WITH CHECK (tenant_id = rag.app_tenant() AND state IN ('staged', 'failed', 'active'));",
        "worker may activate versions",
        DB,
    ),
    (
        MIG,
        "USING (tenant_id = rag.app_tenant() AND state = 'staged')",
        "USING (tenant_id = rag.app_tenant())",
        "worker may modify non-staged versions",
        DB,
    ),
    (
        MIG,
        "CREATE POLICY chunks_worker_insert ON rag.chunks FOR INSERT TO rag_worker\n  WITH CHECK (tenant_id = rag.app_tenant() AND EXISTS (",
        "CREATE POLICY chunks_worker_insert ON rag.chunks FOR INSERT TO rag_worker\n  WITH CHECK (tenant_id = rag.app_tenant() OR EXISTS (",
        "worker may insert chunks of non-staged versions",
        DB,
    ),
    # A DELETE also needs the SELECT policy (PostgreSQL applies both), so loosening either one alone is
    # masked by the other: a layered defence. They are mutated as a pair, as in the Chapter 15 harness.
    (
        MIG,
        (
            "CREATE POLICY chunks_worker_delete ON rag.chunks FOR DELETE TO rag_worker\n  USING (tenant_id = rag.app_tenant() AND EXISTS (",
            "CREATE POLICY chunks_worker_select ON rag.chunks FOR SELECT TO rag_worker\n  USING (tenant_id = rag.app_tenant() AND EXISTS (",
        ),
        (
            "CREATE POLICY chunks_worker_delete ON rag.chunks FOR DELETE TO rag_worker\n  USING (tenant_id = rag.app_tenant() OR EXISTS (",
            "CREATE POLICY chunks_worker_select ON rag.chunks FOR SELECT TO rag_worker\n  USING (tenant_id = rag.app_tenant() OR EXISTS (",
        ),
        "worker may delete chunks of non-staged versions (delete and select policies loosened together)",
        DB,
    ),
    (
        MIG,
        "GRANT SELECT (tenant_id, document_id, version) ON rag.chunks TO rag_worker;",
        "GRANT SELECT (tenant_id, document_id, version, content) ON rag.chunks TO rag_worker;",
        "worker can read chunk content",
        DB,
    ),
    (
        MIG,
        "GRANT SELECT (tenant_id, document_id, status, acl_groups) ON rag.documents TO rag_worker;",
        "GRANT SELECT (tenant_id, document_id, status, acl_groups, title) ON rag.documents TO rag_worker;",
        "worker can read document titles",
        DB,
    ),
    (
        MIG,
        "GRANT UPDATE (state, extractor, failure_reason) ON rag.document_versions TO rag_worker;",
        "GRANT UPDATE (state, extractor, failure_reason, content_sha256) ON rag.document_versions TO rag_worker;",
        "worker can rewrite content hashes",
        DB,
    ),
    (
        MIG,
        "CREATE POLICY documents_worker_select ON rag.documents FOR SELECT TO rag_worker\n  USING (tenant_id = rag.app_tenant());",
        "CREATE POLICY documents_worker_select ON rag.documents FOR SELECT TO rag_worker\n  USING (true);",
        "worker reads documents of every tenant",
        DB,
    ),
    (
        MIG,
        "CREATE POLICY versions_worker_select ON rag.document_versions FOR SELECT TO rag_worker\n  USING (tenant_id = rag.app_tenant());",
        "CREATE POLICY versions_worker_select ON rag.document_versions FOR SELECT TO rag_worker\n  USING (true);",
        "worker reads versions of every tenant",
        DB,
    ),
]


def run_tests(tests: list[str], *, show_failure: bool = False) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-c", "pyproject.toml", *tests]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argument list
            cmd,
            cwd=BACKEND,
            capture_output=True,
            check=False,
            env=os.environ,
            timeout=RUN_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        if show_failure:
            print("tests timed out")
        return False
    if show_failure and result.returncode != 0:  # a failing BASELINE must be diagnosable
        print(result.stdout.decode(errors="replace")[-3000:])
    return result.returncode == 0


def main() -> int:
    needed = (
        "RAG_TEST_ADMIN_URL",
        "RAG_TEST_OWNER_PASSWORD",
        "RAG_TEST_APP_PASSWORD",
        "RAG_TEST_WORKER_PASSWORD",
    )
    if DB and not all(k in os.environ for k in needed):  # database-free suites pass an empty DB list
        print("set the RAG_TEST_* variables first (python scripts/pg_test_env.py)")
        return 2
    for group, tests in (("unit", UNIT), ("database", DB)):
        if not tests:
            continue
        if not run_tests(tests, show_failure=True):
            print(f"baseline {group} tests fail: fix them before mutation testing")
            return 2
    only = sys.argv[1] if len(sys.argv) > 1 else None
    survived: list[str] = []
    ran = 0
    for path, original, mutated, description, tests in MUTANTS:
        if only and only not in description:
            continue
        ran += 1
        pairs = (
            list(zip(original, mutated, strict=True))
            if isinstance(original, tuple)
            else [(original, mutated)]
        )
        source = path.read_text(encoding="utf-8")
        if any(o not in source for o, _ in pairs):  # type: ignore[operator]
            print(f"PATTERN MISSING: {description}", flush=True)
            survived.append(f"pattern missing: {description}")
            continue
        mutated_source = source
        for o, m in pairs:
            mutated_source = mutated_source.replace(o, m, 1)  # type: ignore[arg-type]
        try:
            path.write_text(mutated_source, encoding="utf-8", newline="\n")
            killed = not run_tests(tests)
        finally:
            path.write_text(source, encoding="utf-8", newline="\n")
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
