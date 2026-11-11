"""The background worker: claim a job, run its handler, record the outcome. Run as a separate process:

    python -m rag_service.jobs.worker

Connects as the rag_worker role (RAG_WORKER_DATABASE_URL). Stops cleanly on SIGTERM/SIGINT.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from collections.abc import Callable

from rag_service.core.config import Settings
from rag_service.core.events import LoggingEventSink
from rag_service.core.logging import configure_logging
from rag_service.db.database import Database
from rag_service.features.chunking.chunker import ChunkConfig
from rag_service.features.embedding.bridge import AsyncBridge
from rag_service.features.embedding.service import ChunkEmbedder, EmbeddingConfig
from rag_service.features.extraction.model import ExtractionLimits
from rag_service.features.extraction.sandbox import SandboxedExtractor
from rag_service.features.ingestion.chunk_store import ChunkStore
from rag_service.features.ingestion.pipeline import IngestPipeline
from rag_service.features.ingestion.storage import FilesystemObjectStore
from rag_service.features.llm import LlmGateway, Sensitivity, build_gateway, load_gateway_config
from rag_service.jobs.handlers import Handler, make_handlers
from rag_service.jobs.queue import JobQueue, PermanentFailure

_log = logging.getLogger("rag.worker")


class JobRunner:
    def __init__(
        self,
        queue: JobQueue,
        handlers: dict[str, Handler],
        *,
        worker_id: str,
        lease_s: float,
        backoff_base_s: float,
        backoff_cap_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._queue = queue
        self._handlers = handlers
        self._worker = worker_id
        self._lease = lease_s
        self._base = backoff_base_s
        self._cap = backoff_cap_s
        self._clock = clock

    def _backoff(self, attempts: int) -> float:
        return float(min(self._cap, self._base * 2.0 ** (attempts - 1)))

    def run_once(self) -> bool:
        """Process at most one job. Returns False when there was nothing to do."""
        job = self._queue.claim(self._worker, self._lease)
        if job is None:
            return False
        started = self._clock()
        handler = self._handlers.get(job.kind)
        ctx_base = {"job_id": str(job.job_id), "kind": job.kind, "attempt": job.attempts}
        try:
            if handler is None:
                raise LookupError("no handler for job kind")
            handler(job)
        except Exception as exc:
            permanent = isinstance(exc, PermanentFailure)
            # a permanent failure carries a short safe reason code; anything else only its class name
            error = (
                f"PermanentFailure:{exc.reason}"
                if isinstance(exc, PermanentFailure)
                else type(exc).__name__
            )
            state = self._queue.fail(
                job, self._worker, error, self._backoff(job.attempts), permanent=permanent
            )
            ctx = {**ctx_base, "state": state or "lease_lost", "error": error}
            _log.warning("job_failed", extra={"ctx": ctx | self._duration(started)})
        else:
            applied = self._queue.succeed(job, self._worker)
            ctx = {**ctx_base, "state": "succeeded" if applied else "lease_lost"}
            _log.info("job_done", extra={"ctx": ctx | self._duration(started)})
        return True

    def _duration(self, started: float) -> dict[str, float]:
        return {"duration_ms": round((self._clock() - started) * 1000, 2)}

    def run_forever(self, stop: threading.Event, poll_s: float) -> None:
        while not stop.is_set():
            if not self.run_once():
                stop.wait(poll_s)


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, json_output=settings.log_json, service_name="rag-worker")
    if settings.worker_database_url is None:
        _log.error("RAG_WORKER_DATABASE_URL is not set")
        return 2
    embedder: ChunkEmbedder | None = None
    bridge: AsyncBridge | None = None
    gateway: LlmGateway | None = None
    if settings.embedding_enabled:
        if settings.llm_config_file is None:
            _log.error(
                "embedding is enabled but RAG_LLM_CONFIG_FILE is not set; "
                "set it, or set RAG_EMBEDDING_ENABLED=false to ingest without vectors"
            )
            return 2
        gateway = build_gateway(
            load_gateway_config(settings.llm_config_file),
            allow_fake=not settings.is_production,
            events=LoggingEventSink(),
        )
        bridge = AsyncBridge()
        embedder = ChunkEmbedder(
            gateway,
            EmbeddingConfig(
                route=settings.embedding_route,
                batch_size=settings.embedding_batch_size,
                max_dimensions=settings.embedding_max_dimensions,
                sensitivity=Sensitivity(settings.embedding_sensitivity),
                call_timeout_s=settings.embedding_call_timeout_s,
            ),
            bridge,
        )
    else:
        _log.warning("embedding_disabled: versions will have chunks but no vectors")
    queue = JobQueue(settings.worker_database_url)
    queue.open()
    store = FilesystemObjectStore(settings.object_store_dir)
    # Content writes use their own small pool, still as rag_worker: the tenant-scoped transaction path.
    content_db = Database(
        settings.worker_database_url,
        min_size=1,
        max_size=2,
        acquire_timeout_s=settings.db_pool_acquire_timeout_s,
        statement_timeout_ms=settings.db_statement_timeout_ms,
        idle_in_transaction_timeout_ms=settings.db_idle_in_transaction_timeout_ms,
    )
    content_db.open()
    pipeline = IngestPipeline(
        store,
        SandboxedExtractor(
            ExtractionLimits(
                timeout_s=settings.extract_timeout_s,
                memory_bytes=settings.extract_memory_mb * 1024 * 1024,
                max_input_bytes=settings.max_upload_bytes,
                max_pages=settings.extract_max_pages,
                max_text_chars=settings.extract_max_text_chars,
                max_zip_members=settings.extract_max_zip_members,
                max_uncompressed_bytes=settings.extract_max_uncompressed_mb * 1024 * 1024,
                max_compression_ratio=settings.extract_max_compression_ratio,
            )
        ),
        ChunkConfig(
            target_tokens=settings.chunk_target_tokens,
            max_tokens=settings.chunk_max_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            chars_per_token=settings.chunk_chars_per_token,
            max_chunks=settings.chunk_max_per_version,
        ),
        ChunkStore(content_db),
        max_input_bytes=settings.max_upload_bytes,
        embedder=embedder,
    )
    runner = JobRunner(
        queue,
        make_handlers(store, queue, pipeline),
        worker_id=f"{socket.gethostname()}-{os.getpid()}",
        lease_s=settings.job_lease_s,
        backoff_base_s=settings.job_backoff_base_s,
        backoff_cap_s=settings.job_backoff_cap_s,
    )
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    _log.info("worker_started")
    try:
        runner.run_forever(stop, settings.job_poll_interval_s)
    finally:
        content_db.close()
        queue.close()
        if bridge is not None and gateway is not None:
            bridge.run(gateway.aclose(), 10)
            bridge.close()
        _log.info("worker_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
