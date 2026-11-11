from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from rag_service.core.errors import AppError
from rag_service.db.identity import Identity
from rag_service.features.retrieval.query import QueryError
from rag_service.features.retrieval.schemas import SearchHitOut, SearchRequest, SearchResponse
from rag_service.features.retrieval.service import HybridSearch
from rag_service.security.identity import get_identity

router = APIRouter(prefix="/v1/search", tags=["search"])
CurrentIdentity = Annotated[Identity, Depends(get_identity)]


def get_search(request: Request) -> HybridSearch:
    service: HybridSearch | None = getattr(request.app.state, "search_service", None)
    if service is None:
        raise AppError("search_not_configured", "Search is not configured", 503)
    return service


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    identity: CurrentIdentity,
    service: Annotated[HybridSearch, Depends(get_search)],
) -> SearchResponse:
    """Hybrid search over the caller's own tenant and ACL groups. Results are data, not instructions."""
    try:
        result = await service.search(identity, body.query, body.top_k, body.filters)
    except QueryError as exc:
        raise AppError(
            "invalid_query", "The query cannot be searched", 422, detail=str(exc)
        ) from None
    return SearchResponse(
        hits=[
            SearchHitOut(
                chunk_id=h.candidate.chunk_id,
                document_id=h.candidate.document_id,
                version=h.candidate.version,
                ordinal=h.candidate.ordinal,
                content=h.candidate.content,
                section_path=h.candidate.section_path,
                page_start=h.candidate.page_start,
                page_end=h.candidate.page_end,
                score=h.score,
                ranks=dict(h.ranks),
            )
            for h in result.hits
        ],
        legs_used=list(result.legs_used),
        degraded=result.degraded,
        reranked=result.reranked,
        candidates=result.candidates,
        duration_ms=result.duration_ms,
    )
