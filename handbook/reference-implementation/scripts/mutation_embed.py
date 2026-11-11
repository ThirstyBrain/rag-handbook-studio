"""Mutation check for chunk embedding (ADR-017): the embedder, the async bridge, the vector write path,
the worker's start-up policy and migration 0004.

Same method and runner as mutation_extract.py (one realistic defect per mutant, expect a test FAILURE,
always restore the file, a pattern that no longer matches is reported). Needs the compose database and
the RAG_TEST_* variables. Run from reference-implementation/backend:
    python ../scripts/mutation_embed.py [description-filter]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_extract as mx  # noqa: E402

FEATURES = mx.FEATURES
SERVICE = FEATURES / "embedding" / "service.py"
BRIDGE = FEATURES / "embedding" / "bridge.py"
WORKER = mx.JOBS / "worker.py"
STORE = mx.STORE
PIPELINE = mx.PIPELINE
MIG = mx.ROOT / "database" / "migrations" / "0004_chunk_embeddings.sql"

UNIT = ["../tests/unit/test_embedding.py"]
DB = [
    "../tests/integration/test_embeddings_db.py",
    "../tests/integration/test_schema_security.py",
    "../tests/integration/test_chunk_pipeline.py",
]

MUTANTS: list[mx.Mutant] = [
    # ---------------------------------------------------------------- embedder
    (SERVICE, "if len(result.vectors) != expected:", "if False:", "vector count not checked", UNIT),
    (
        SERVICE,
        "if not all(math.isfinite(x) for x in vector):",
        "if False:",
        "non-finite values accepted",
        UNIT,
    ),
    (SERVICE, "if not any(vector):", "if False:", "zero vector accepted", UNIT),
    (
        SERVICE,
        "if len(vector) != result.dimensions:",
        "if False:",
        "vector length not checked against the dimension",
        UNIT,
    ),
    (
        SERVICE,
        "elif result.embedding_space != space or result.dimensions != dims:",
        "elif False:",
        "embedding space may change inside one version",
        UNIT,
    ),
    (
        SERVICE,
        "if not result.embedding_space:",
        "if False:",
        "route without an embedding space accepted",
        UNIT,
    ),
    (
        SERVICE,
        "if not 1 <= result.dimensions <= self._config.max_dimensions:",
        "if False:",
        "dimension limit ignored",
        UNIT,
    ),
    (
        SERVICE,
        "except (InvalidRequest, ContentRefused):",
        "except ContentRefused:",
        "oversized input retried forever instead of failing the version",
        UNIT,
    ),
    (
        SERVICE,
        'return f"{chunk.section_path}\\n\\n{chunk.content}" if chunk.section_path else chunk.content',
        "return chunk.content",
        "section path not embedded",
        UNIT + DB[:1],
    ),
    (
        SERVICE,
        "models.extend([result.model] * len(batch))",
        "models.extend([models[0] if models else result.model] * len(batch))",
        "model recorded wrongly after a fallback",
        UNIT,
    ),
    (
        SERVICE,
        "for start in range(0, len(texts), size):",
        "for start in range(0, len(texts), size + 1):",
        "chunks skipped between batches",
        UNIT,
    ),
    (
        SERVICE,
        "self._gateway.embed(request), self._config.call_timeout_s",
        "self._gateway.embed(request), 10_000",
        "call timeout ignored",
        UNIT,
    ),
    (
        SERVICE,
        "sensitivity=self._config.sensitivity",
        "sensitivity=Sensitivity.INTERNAL",
        "data sensitivity not passed to the gateway",
        UNIT,
    ),
    # ---------------------------------------------------------------- bridge and worker policy
    (BRIDGE, "future.cancel()", "pass", "timed-out call keeps running", UNIT),
    (
        WORKER,
        "if settings.llm_config_file is None:",
        "if False:",
        "worker starts with embedding enabled and no gateway",
        UNIT,
    ),
    # ---------------------------------------------------------------- vector write path
    (
        STORE,
        "digest = hashlib.sha256(chunk.content.encode()).hexdigest()[:32]",
        'digest = ""',
        "chunk id ignores content",
        UNIT,
    ),
    (STORE, "embeddings.recipe,", '"x",', "recipe not stored", DB[:1]),
    (
        STORE,
        'return "[" + ",".join(repr(float(x)) for x in vector) + "]"',
        'return "[" + ",".join(str(round(float(x), 2)) for x in vector) + "]"',
        "vector precision lost on write",
        DB[:1],
    ),
    (
        PIPELINE,
        "embedded = self._embedder.embed(chunks) if self._embedder is not None else None",
        "embedded = None",
        "embeddings computed but never stored",
        DB[:1],
    ),
    # ---------------------------------------------------------------- migration 0004
    (
        MIG,
        "GRANT INSERT ON rag.chunk_embeddings TO rag_worker;",
        "GRANT SELECT, INSERT ON rag.chunk_embeddings TO rag_worker;",
        "worker can read embeddings",
        DB,
    ),
    (
        MIG,
        "GRANT INSERT ON rag.chunk_embeddings TO rag_worker;",
        "GRANT INSERT, UPDATE, DELETE ON rag.chunk_embeddings TO rag_worker;",
        "worker can update and delete embeddings",
        DB,
    ),
    (
        MIG,
        "GRANT SELECT ON rag.chunk_embeddings TO rag_app;",
        "GRANT SELECT, INSERT, DELETE ON rag.chunk_embeddings TO rag_app;",
        "app can write embeddings",
        DB,
    ),
    (
        MIG,
        (
            "USING (tenant_id = rag.app_tenant() AND EXISTS (\n"
            "    SELECT 1 FROM rag.chunks c\n"
            "    WHERE c.tenant_id = chunk_embeddings.tenant_id AND c.chunk_id = chunk_embeddings.chunk_id));"
        ),
        "USING (tenant_id = rag.app_tenant());",
        "embeddings ignore the chunk ACL",
        DB,
    ),
    (
        MIG,
        (
            "WITH CHECK (tenant_id = rag.app_tenant() AND EXISTS (\n"
            "    SELECT 1 FROM rag.chunks c\n"
            "    WHERE c.tenant_id = chunk_embeddings.tenant_id AND c.chunk_id = chunk_embeddings.chunk_id));"
        ),
        "WITH CHECK (tenant_id = rag.app_tenant());",
        "worker can add vectors to chunks it cannot see (non-staged)",
        DB,
    ),
    (
        MIG,
        "GRANT SELECT (chunk_id) ON rag.chunks TO rag_worker;",
        "GRANT SELECT ON rag.chunks TO rag_worker;",
        "worker can read chunk content",
        DB,
    ),
    (
        MIG,
        "CHECK (vector_dims(embedding) = dimensions)",
        "CHECK (true)",
        "stored vector may disagree with its recorded dimension",
        DB,
    ),
    (
        MIG,
        "ON DELETE CASCADE",
        "ON DELETE NO ACTION",
        "vectors block chunk replacement and document deletion",
        DB,
    ),
    (
        MIG,
        "ALTER TABLE rag.chunk_embeddings FORCE  ROW LEVEL SECURITY;",
        "",
        "row security not forced on embeddings",
        DB,
    ),
]


if __name__ == "__main__":
    mx.UNIT, mx.DB, mx.MUTANTS = UNIT, DB, MUTANTS
    raise SystemExit(mx.main())
