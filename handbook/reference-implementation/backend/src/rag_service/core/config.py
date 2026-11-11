"""Application settings. Every tunable value lives here; nothing is hard-coded elsewhere.

Values come from environment variables prefixed ``RAG_`` (and an optional ``.env`` file for local
development). Secrets use ``SecretStr`` so they do not appear in ``repr`` or logs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    environment: Environment = "local"
    service_name: str = "rag-service"
    log_level: LogLevel = "INFO"
    log_json: bool = True

    # Application connection (the restricted rag_app role). None: no database configured.
    database_url: SecretStr | None = None
    # Migration connection (the rag_owner role). Used only by `python -m rag_service.db.migrate`.
    migration_database_url: SecretStr | None = None
    migrations_dir: Path = Path("database/migrations")
    db_pool_min_size: int = Field(default=1, ge=0, le=100)
    db_pool_max_size: int = Field(default=10, ge=1, le=200)
    db_pool_acquire_timeout_s: float = Field(default=5.0, gt=0, le=60)
    db_statement_timeout_ms: int = Field(default=30_000, ge=100, le=600_000)
    db_idle_in_transaction_timeout_ms: int = Field(default=15_000, ge=100, le=600_000)
    readiness_check_timeout_s: float = Field(default=2.0, gt=0, le=30)

    # Background worker connection (the rag_worker role: job queue access only).
    worker_database_url: SecretStr | None = None
    job_lease_s: float = Field(default=300.0, gt=0, le=3600)
    job_poll_interval_s: float = Field(default=1.0, gt=0, le=60)
    job_max_attempts: int = Field(default=5, ge=1, le=20)
    job_backoff_base_s: float = Field(default=5.0, ge=0, le=600)
    job_backoff_cap_s: float = Field(default=300.0, ge=0, le=3600)

    # Ingestion.
    object_store_dir: Path = Path("data/objects")
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0, le=1024**3)
    # Extraction runs in a child process with these limits (ADR-016). Files are hostile input.
    extract_timeout_s: float = Field(default=30.0, gt=0, le=600)
    extract_memory_mb: int = Field(default=1024, ge=64, le=16_384)  # POSIX only (RLIMIT_AS)
    extract_max_pages: int = Field(default=1000, ge=1, le=100_000)
    extract_max_text_chars: int = Field(default=5_000_000, ge=1000, le=200_000_000)
    extract_max_zip_members: int = Field(default=2000, ge=1, le=100_000)
    extract_max_uncompressed_mb: int = Field(default=100, ge=1, le=4096)
    extract_max_compression_ratio: float = Field(default=100.0, gt=1, le=10_000)
    # Chunking (ADR-003; sizes are starting hypotheses to be tuned by the golden set, component 17).
    chunk_target_tokens: int = Field(default=512, ge=32, le=8000)
    chunk_max_tokens: int = Field(default=768, ge=32, le=8000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=2000)
    chunk_chars_per_token: float = Field(default=4.0, gt=0.5, le=16)
    chunk_max_per_version: int = Field(default=20_000, ge=1, le=1_000_000)

    # Embedding of chunks during ingestion, through the gateway's embed route (ADR-017). The worker refuses
    # to start with embedding enabled and no gateway, so a misconfiguration cannot silently produce
    # versions that have chunks but no vectors.
    embedding_enabled: bool = True
    embedding_route: str = Field(default="embed", min_length=1, max_length=64)
    embedding_batch_size: int = Field(default=32, ge=1, le=2048)
    embedding_max_dimensions: int = Field(
        default=4000, ge=1, le=4000
    )  # pgvector halfvec index limit
    embedding_sensitivity: Literal["public", "internal", "restricted"] = "internal"
    embedding_call_timeout_s: float = Field(default=120.0, gt=0, le=900)

    # Hybrid retrieval (ADR-004, ADR-009, ADR-019). Starting hypotheses, to be tuned by the golden set
    # (component 17); none has been measured. The query is embedded through the same route as documents.
    retrieval_candidates_per_leg: int = Field(default=50, ge=1, le=1000)
    retrieval_max_top_k: int = Field(default=50, ge=1, le=1000)
    retrieval_rrf_k: int = Field(default=60, ge=1, le=1000)
    retrieval_fts_weight: float = Field(default=1.0, ge=0, le=100)
    retrieval_vector_weight: float = Field(default=1.0, ge=0, le=100)
    retrieval_embed_timeout_s: float = Field(default=10.0, gt=0, le=120)
    retrieval_ef_search: int = Field(default=100, ge=1, le=1000)
    retrieval_iterative_scan: Literal["off", "relaxed_order", "strict_order"] = "relaxed_order"

    # Reranking (ADR-008): off by default because the only built-in reranker is a lexical BM25 baseline whose
    # benefit is unmeasured. A failure always falls back to first-stage order.
    rerank_enabled: bool = False
    rerank_candidates: int = Field(default=30, ge=1, le=1000)
    rerank_timeout_s: float = Field(default=2.0, gt=0, le=60)
    rerank_breaker_threshold: int = Field(default=5, ge=1, le=1000)
    rerank_breaker_reset_s: float = Field(default=30.0, gt=0, le=3600)

    # DEVELOPMENT ONLY: trust X-Dev-* headers as the caller's identity until authentication (component 13)
    # exists. Refused in production by the validator below.
    dev_identity_enabled: bool = False

    # Path to the LLM gateway TOML (see config/llm-gateway.example.toml). None disables the gateway.
    llm_config_file: Path | None = None

    request_id_header: str = "X-Request-ID"
    request_id_max_length: int = Field(default=64, ge=8, le=128)
    expose_api_docs: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _no_dev_identity_in_production(self) -> Self:
        if self.dev_identity_enabled and self.environment == "production":
            raise ValueError("dev_identity_enabled must not be set when environment is production")
        return self
