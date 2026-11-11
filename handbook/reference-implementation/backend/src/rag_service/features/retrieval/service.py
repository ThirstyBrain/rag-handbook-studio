"""Hybrid search: embed the query, run both legs in one tenant-scoped transaction, fuse with RRF.

Degradation is explicit and reported, never silent: if the query cannot be embedded (provider outage,
timeout, budget, no gateway) the lexical leg still answers and the response says the vector leg was
unavailable. Chunk text is returned as DATA for the caller; nothing here follows or interprets it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from rag_service.core.events import EventSink
from rag_service.db.database import Conn, Database
from rag_service.db.identity import Identity
from rag_service.features.indexing.ddl import IndexSpecError, VectorIndexSpec
from rag_service.features.llm import EmbedRequest, EmbedResult
from rag_service.features.llm.errors import LlmError
from rag_service.features.llm.types import Sensitivity
from rag_service.features.reranking.apply import apply_scores
from rag_service.features.reranking.guard import GuardedReranker
from rag_service.features.reranking.ports import RerankItem
from rag_service.features.retrieval.filters import Condition, compile_filters
from rag_service.features.retrieval.fusion import Candidate, FusedHit, reciprocal_rank_fusion
from rag_service.features.retrieval.query import (
    QueryError,
    normalise_query,
    validate_query_vector,
)
from rag_service.features.retrieval.repository import fts_candidates, vector_candidates

_log = logging.getLogger(__name__)
SEARCH_COMPLETED = "search_completed"
Leg = Literal["fts", "vector"]


class EmbedPort(Protocol):
    async def embed(self, request: EmbedRequest) -> EmbedResult: ...


@dataclass(frozen=True)
class RetrievalConfig:
    embedding_route: str = "embed"
    embedding_sensitivity: Sensitivity = Sensitivity.INTERNAL
    embed_timeout_s: float = 10.0
    max_dimensions: int = 4000
    candidates_per_leg: int = 50
    rrf_k: int = 60
    fts_weight: float = 1.0
    vector_weight: float = 1.0
    ef_search: int = 100
    iterative_scan: Literal["off", "relaxed_order", "strict_order"] = "relaxed_order"
    max_top_k: int = 50
    # How many fused candidates are sent to the reranker (ADR-008 decision 4: N must come from the measured
    # candidate recall@N curve; this default is a placeholder, not a measurement). Used only with a reranker.
    rerank_candidates: int = 30

    def __post_init__(self) -> None:
        if not 1 <= self.rerank_candidates <= 1000:
            raise ValueError("rerank_candidates must be between 1 and 1000")
        if not (
            1 <= self.candidates_per_leg <= 1000 and 1 <= self.max_top_k <= self.candidates_per_leg
        ):
            raise ValueError("invalid retrieval limits")
        if self.embed_timeout_s <= 0 or not 1 <= self.ef_search <= 1000:
            raise ValueError("invalid retrieval timeouts or ef_search")


@dataclass(frozen=True)
class SearchResult:
    hits: list[FusedHit]
    legs_used: list[Leg]
    degraded: list[str] = field(
        default_factory=list
    )  # short safe codes, e.g. "vector:provider_error"
    candidates: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    reranked: bool = False


class HybridSearch:
    def __init__(
        self,
        db: Database,
        gateway: EmbedPort | None,
        config: RetrievalConfig,
        events: EventSink,
        clock: Callable[[], float] = time.monotonic,
        reranker: GuardedReranker | None = None,
    ) -> None:
        self._reranker = reranker
        self._db = db
        self._gateway = gateway
        self._config = config
        self._events = events
        self._clock = clock

    async def search(
        self,
        identity: Identity,
        query: str,
        top_k: int = 10,
        filters: Sequence[Condition] = (),
    ) -> SearchResult:
        started = self._clock()
        text = normalise_query(query)
        if not 1 <= top_k <= self._config.max_top_k:
            raise QueryError(f"top_k must be between 1 and {self._config.max_top_k}")
        flt = compile_filters(filters)  # invalid filters fail before any provider call is paid for

        spec, vector, degraded = await self._embed(text)
        cfg = self._config

        def work(conn: Conn) -> dict[str, list[Candidate]]:
            found = {"fts": fts_candidates(conn, text, cfg.candidates_per_leg, flt)}
            if spec is not None and vector is not None:
                found["vector"] = vector_candidates(
                    conn, spec, vector, cfg.candidates_per_leg,
                    ef_search=cfg.ef_search, iterative_scan=cfg.iterative_scan, flt=flt,
                )  # fmt: skip
            return found

        found = await self._db.run(identity, work)
        legs_used: list[Leg] = ["fts", "vector"] if "vector" in found else ["fts"]
        fused = reciprocal_rank_fusion(
            found,
            k=cfg.rrf_k,
            weights={"fts": cfg.fts_weight, "vector": cfg.vector_weight},
            limit=max(top_k, cfg.rerank_candidates) if self._reranker else top_k,
        )
        hits, reranked = fused[:top_k], False
        if self._reranker is not None and fused:
            # Authorize first: these candidates already passed tenant, ACL and lifecycle filters in SQL, so
            # only authorized text reaches the reranker (ADR-008 decision 3).
            scores, reason = await self._reranker.rerank(
                text, [RerankItem(h.candidate.content) for h in fused]
            )
            if scores is not None:
                hits, reranked = apply_scores(fused, scores, top_k), True
            elif reason is not None:
                # first-stage order is kept; the fallback is reported, never silent
                degraded = [*degraded, reason]
        result = SearchResult(
            hits=hits,
            legs_used=legs_used,
            degraded=degraded,
            candidates={name: len(items) for name, items in found.items()},
            duration_ms=round((self._clock() - started) * 1000, 2),
            reranked=reranked,
        )
        # Events carry counts and codes only, never the query text or chunk content.
        self._events.emit(
            SEARCH_COMPLETED,
            {
                "legs": "+".join(legs_used),
                "degraded": len(degraded),
                "hits": len(hits),
                "reranked": int(reranked),
                "duration_ms": result.duration_ms,
            },
        )
        return result

    async def _embed(
        self, text: str
    ) -> tuple[VectorIndexSpec | None, list[float] | None, list[str]]:
        if self._gateway is None:
            return None, None, ["vector:not_configured"]
        cfg = self._config
        request = EmbedRequest(
            route=cfg.embedding_route, inputs=[text], sensitivity=cfg.embedding_sensitivity
        )
        try:
            result = await asyncio.wait_for(self._gateway.embed(request), cfg.embed_timeout_s)
            if len(result.vectors) != 1:
                raise QueryError("unexpected number of query embeddings")
            vector = result.vectors[0]
            validate_query_vector(vector, result.dimensions, cfg.max_dimensions)
            return VectorIndexSpec(result.embedding_space, result.dimensions), vector, []
        except TimeoutError:
            return None, None, ["vector:timeout"]
        except LlmError as exc:
            _log.warning("query_embedding_failed", extra={"ctx": {"error": type(exc).__name__}})
            return None, None, ["vector:provider_error"]
        except (QueryError, IndexSpecError) as exc:
            _log.warning("query_embedding_invalid", extra={"ctx": {"error": type(exc).__name__}})
            return None, None, ["vector:invalid_embedding"]
