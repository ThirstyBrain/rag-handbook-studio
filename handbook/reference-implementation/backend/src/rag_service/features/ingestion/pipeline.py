"""The ingestion pipeline for one staged version: read, extract (sandboxed), chunk, store (ADR-016).

Failure policy: a file the pipeline cannot process (``Rejected``) is recorded on the version as ``failed``
with a safe reason code and the job ends permanently, because a retry would fail the same way.
Infrastructure faults (database, storage, sandbox start-up) propagate and the job is retried.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Protocol

from rag_service.features.chunking.chunker import (
    CHUNKER_VERSION,
    Chunk,
    ChunkConfig,
    chunk_blocks,
)
from rag_service.features.embedding.service import EmbeddedChunks
from rag_service.features.extraction.model import Extracted, Rejected
from rag_service.features.ingestion.chunk_store import ChunkStore
from rag_service.features.ingestion.storage import ObjectStore
from rag_service.jobs.queue import Job, PermanentFailure

_log = logging.getLogger("rag.ingest")


class Extractor(Protocol):
    def extract(self, media_type: str, data: bytes) -> Extracted: ...


class Embedder(Protocol):
    def embed(self, chunks: Sequence[Chunk]) -> EmbeddedChunks: ...


class IngestPipeline:
    def __init__(
        self,
        store: ObjectStore,
        extractor: Extractor,
        chunk_config: ChunkConfig,
        chunks: ChunkStore,
        *,
        max_input_bytes: int,
        embedder: Embedder | None = None,
    ) -> None:
        self._store = store
        self._extractor = extractor
        self._config = chunk_config
        self._chunks = chunks
        self._max = max_input_bytes
        self._embedder = embedder

    def _read(self, key: str) -> bytes:
        with self._store.open(key) as handle:
            data = handle.read(self._max + 1)
        if len(data) > self._max:
            raise Rejected("input_too_large")
        return data

    def process(self, job: Job, key: str, media_type: str) -> None:
        """Read the verified object ``key``, then extract, chunk and store it for the job's version."""
        if job.document_id is None or job.version is None:
            raise PermanentFailure("bad_job")
        started = time.monotonic()
        try:
            extracted = self._extractor.extract(media_type, self._read(key))
            chunks = chunk_blocks(extracted.blocks, self._config)
            if not chunks:
                raise Rejected("no_text")
            # Embedding is a network call: it happens before, and outside, the database transaction.
            embedded = self._embedder.embed(chunks) if self._embedder is not None else None
        except Rejected as exc:
            self._chunks.mark_failed(job.tenant_id, job.document_id, job.version, exc.reason)
            raise PermanentFailure(exc.reason) from None
        outcome = self._chunks.replace_chunks(
            job.tenant_id, job.document_id, job.version, chunks,
            extractor=extracted.extractor, chunker=CHUNKER_VERSION, embeddings=embedded,
        )  # fmt: skip
        if outcome == "written":
            # A second transaction: chunks and vectors are already complete and atomic, so a failure here
            # leaves a complete staged version (invisible to retrieval); the job's retry repeats the whole
            # idempotent job, including the embedding call.
            activation = self._chunks.activate_version(job.tenant_id, job.document_id, job.version)
            if activation == "stale":
                outcome = "stale"
        _log.info(
            "ingest_processed",
            extra={
                "ctx": {
                    "job_id": str(job.job_id),
                    "outcome": outcome,
                    "blocks": len(extracted.blocks),
                    "chunks": len(chunks),
                    "extractor": extracted.extractor,
                    "embedded": embedded is not None,
                    "embedding_space": embedded.space if embedded else None,
                    "embedding_tokens": embedded.input_tokens if embedded else 0,
                    "embedding_calls": embedded.calls if embedded else 0,
                    "embedding_fallback": embedded.fallback_used if embedded else False,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                }
            },
        )
