"""Application factory. Run with: uvicorn rag_service.main:create_app --factory"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rag_service import __version__
from rag_service.core.config import Settings
from rag_service.core.errors import register_error_handlers
from rag_service.core.events import APP_STARTED, EventSink, LoggingEventSink
from rag_service.core.logging import configure_logging
from rag_service.core.middleware import RequestContextMiddleware
from rag_service.db.database import Database
from rag_service.db.migrate import expected_version
from rag_service.features.health.postgres_check import PostgresCheck
from rag_service.features.health.router import router as health_router
from rag_service.features.health.schema_check import SchemaVersionCheck
from rag_service.features.health.service import HealthService, ReadinessCheck
from rag_service.features.ingestion.router import router as ingestion_router
from rag_service.features.ingestion.service import IngestionService
from rag_service.features.ingestion.storage import FilesystemObjectStore
from rag_service.features.llm import LlmGateway, build_gateway, load_gateway_config
from rag_service.features.llm.http import register_llm_error_handlers
from rag_service.features.llm.types import Sensitivity
from rag_service.features.reranking.guard import GuardedReranker
from rag_service.features.reranking.lexical import Bm25Reranker
from rag_service.features.retrieval.router import router as search_router
from rag_service.features.retrieval.service import HybridSearch, RetrievalConfig

_log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    checks: Sequence[ReadinessCheck] | None = None,
    events: EventSink | None = None,
    gateway: LlmGateway | None = None,
    configure_logs: bool = True,
) -> FastAPI:
    """Build the app. ``checks``, ``events`` and ``gateway`` are injection points (tests, features)."""
    settings = settings or Settings()
    if configure_logs:
        configure_logging(
            settings.log_level, json_output=settings.log_json, service_name=settings.service_name
        )
    sink = events or LoggingEventSink()

    if checks is None:
        checks = []
        if settings.database_url is not None:
            checks = [
                PostgresCheck(settings.database_url, timeout_s=settings.readiness_check_timeout_s)
            ]
            if settings.migrations_dir.is_dir():
                checks.append(
                    SchemaVersionCheck(
                        settings.database_url,
                        expected_version=expected_version(settings.migrations_dir),
                        timeout_s=settings.readiness_check_timeout_s,
                    )
                )
            else:
                _log.warning(
                    "migrations_dir_missing", extra={"ctx": {"dir": str(settings.migrations_dir)}}
                )

    db: Database | None = None
    if settings.database_url is not None:
        db = Database(
            settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            acquire_timeout_s=settings.db_pool_acquire_timeout_s,
            statement_timeout_ms=settings.db_statement_timeout_ms,
            idle_in_transaction_timeout_ms=settings.db_idle_in_transaction_timeout_ms,
        )

    llm_gateway: LlmGateway | None = None
    if gateway is not None:
        llm_gateway = gateway
    elif settings.llm_config_file is not None:
        # In production the fake provider is refused; strict mode (in the file) can refuse to start.
        llm_gateway = build_gateway(
            load_gateway_config(settings.llm_config_file),
            allow_fake=not settings.is_production,
            events=sink,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        sink.emit(APP_STARTED, {"environment": settings.environment, "version": __version__})
        _log.info(
            "startup", extra={"ctx": {"environment": settings.environment, "version": __version__}}
        )
        if db is not None:
            db.open()
        yield
        if llm_gateway is not None:
            await llm_gateway.aclose()
        if db is not None:
            await asyncio.to_thread(db.close)
        _log.info("shutdown")

    docs = settings.expose_api_docs and not settings.is_production
    app = FastAPI(
        title="RAG reference service",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.llm_gateway = llm_gateway
    app.state.database = db
    app.state.ingestion_service = (
        IngestionService(
            db,
            FilesystemObjectStore(settings.object_store_dir),
            max_upload_bytes=settings.max_upload_bytes,
            job_max_attempts=settings.job_max_attempts,
        )
        if db is not None
        else None
    )
    app.state.search_service = (
        HybridSearch(
            db,
            llm_gateway,
            RetrievalConfig(
                embedding_route=settings.embedding_route,
                embedding_sensitivity=Sensitivity(settings.embedding_sensitivity),
                embed_timeout_s=settings.retrieval_embed_timeout_s,
                max_dimensions=settings.embedding_max_dimensions,
                candidates_per_leg=settings.retrieval_candidates_per_leg,
                rrf_k=settings.retrieval_rrf_k,
                fts_weight=settings.retrieval_fts_weight,
                vector_weight=settings.retrieval_vector_weight,
                ef_search=settings.retrieval_ef_search,
                iterative_scan=settings.retrieval_iterative_scan,
                max_top_k=min(settings.retrieval_max_top_k, settings.retrieval_candidates_per_leg),
                rerank_candidates=settings.rerank_candidates,
            ),
            sink,
            reranker=(
                GuardedReranker(
                    Bm25Reranker(),
                    timeout_s=settings.rerank_timeout_s,
                    breaker_threshold=settings.rerank_breaker_threshold,
                    breaker_reset_s=settings.rerank_breaker_reset_s,
                )
                if settings.rerank_enabled
                else None
            ),
        )
        if db is not None
        else None
    )
    app.state.health_service = HealthService(
        checks, timeout_s=settings.readiness_check_timeout_s, events=sink
    )
    register_error_handlers(app)
    register_llm_error_handlers(app)
    app.add_middleware(
        RequestContextMiddleware,
        header_name=settings.request_id_header,
        max_id_length=settings.request_id_max_length,
    )
    app.include_router(health_router)
    app.include_router(ingestion_router)
    app.include_router(search_router)
    return app
