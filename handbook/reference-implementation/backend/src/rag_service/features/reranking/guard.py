"""Timeout, circuit breaker and validation around any reranker; failure means first-stage order (ADR-008).

A reranker is an optional quality stage, never a dependency of correctness: any failure (timeout, error,
open breaker, malformed scores) yields ``None`` plus a short safe reason, and the caller keeps the
first-stage order. The reason is surfaced to the API and to a metric so fallbacks are never silent.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable, Sequence

from rag_service.features.llm.gateway import CircuitBreaker
from rag_service.features.reranking.ports import Reranker, RerankError, RerankItem

_log = logging.getLogger(__name__)


class GuardedReranker:
    def __init__(
        self,
        inner: Reranker,
        *,
        timeout_s: float,
        breaker_threshold: int = 5,
        breaker_reset_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._inner = inner
        self._timeout_s = timeout_s
        self._breaker = CircuitBreaker(breaker_threshold, breaker_reset_s, clock)

    @property
    def name(self) -> str:
        return self._inner.name

    async def rerank(
        self, query: str, items: Sequence[RerankItem]
    ) -> tuple[list[float] | None, str | None]:
        """Return ``(scores, None)`` or ``(None, reason)``; never raises for reranker problems."""
        if not items:
            return [], None
        if not self._breaker.allow():
            return None, "rerank:circuit_open"
        try:
            scores = await asyncio.wait_for(self._inner.rerank(query, items), self._timeout_s)
            self._validate(scores, len(items))
        except TimeoutError:
            self._breaker.failure()
            return None, "rerank:timeout"
        except RerankError:
            self._breaker.failure()
            return None, "rerank:invalid_scores"
        except Exception as exc:
            _log.warning("rerank_failed", extra={"ctx": {"error": type(exc).__name__}})
            self._breaker.failure()
            return None, "rerank:error"
        self._breaker.success()
        return scores, None

    @staticmethod
    def _validate(scores: list[float], expected: int) -> None:
        if len(scores) != expected or not all(math.isfinite(s) for s in scores):
            raise RerankError("reranker returned the wrong number of scores or non-finite values")
