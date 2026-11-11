"""Build a real ingestion pipeline (rag_worker database access, object store) for integration tests."""

from __future__ import annotations

from pathlib import Path

from pg import ScratchDb
from pydantic import SecretStr

from rag_service.db.database import Database
from rag_service.features.chunking.chunker import ChunkConfig
from rag_service.features.extraction.dispatch import extract
from rag_service.features.extraction.model import Extracted, ExtractionLimits
from rag_service.features.ingestion.chunk_store import ChunkStore
from rag_service.features.ingestion.pipeline import Embedder, Extractor, IngestPipeline
from rag_service.features.ingestion.storage import FilesystemObjectStore


class InProcessExtractor:
    """TEST DOUBLE: runs the real parsers without the child process, for speed. The sandbox itself is
    tested in tests/unit/test_extraction_sandbox.py and once end to end in test_chunk_pipeline.py."""

    def __init__(self, limits: ExtractionLimits | None = None) -> None:
        self._limits = limits or ExtractionLimits()

    def extract(self, media_type: str, data: bytes) -> Extracted:
        return extract(media_type, data, self._limits)


class Rig:
    def __init__(
        self,
        db: ScratchDb,
        objects: Path,
        *,
        extractor: Extractor | None = None,
        config: ChunkConfig | None = None,
        max_input_bytes: int = 1024 * 1024,
        embedder: Embedder | None = None,
    ) -> None:
        self.content_db = Database(
            SecretStr(db.worker_url),
            min_size=1,
            max_size=3,
            acquire_timeout_s=5,
            statement_timeout_ms=30_000,
            idle_in_transaction_timeout_ms=15_000,
        )
        self.content_db.open()
        self.store = FilesystemObjectStore(objects)
        self.chunks = ChunkStore(self.content_db)
        self.pipeline = IngestPipeline(
            self.store,
            extractor or InProcessExtractor(),
            config or ChunkConfig(),
            self.chunks,
            max_input_bytes=max_input_bytes,
            embedder=embedder,
        )

    def close(self) -> None:
        self.content_db.close()
