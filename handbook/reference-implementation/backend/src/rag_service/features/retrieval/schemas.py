from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rag_service.features.retrieval.filters import Condition


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=10, ge=1, le=100)
    # Allow-listed metadata conditions (ADR-009); they can only narrow what the caller may already see.
    filters: list[Condition] = Field(default_factory=list, max_length=8)


class SearchHitOut(BaseModel):
    chunk_id: UUID
    document_id: UUID
    version: int
    ordinal: int
    content: str
    section_path: str | None
    page_start: int | None
    page_end: int | None
    score: float
    ranks: dict[str, int]


class SearchResponse(BaseModel):
    hits: list[SearchHitOut]
    legs_used: list[str]
    degraded: list[str]
    reranked: bool
    candidates: dict[str, int]
    duration_ms: float
