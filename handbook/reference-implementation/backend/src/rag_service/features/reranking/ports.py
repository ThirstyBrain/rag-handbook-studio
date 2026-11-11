"""The reranker port (ADR-008 decision 2).

A reranker receives the query and ONLY already-authorized candidate texts (tenant, ACL and lifecycle filters
ran inside retrieval, ADR-004/ADR-009) and returns one relevance score per candidate, aligned by position.
Scores are comparable only within one call: callers must never threshold them or compare them across calls,
models or versions (ADR-008 decision 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RerankItem:
    text: str  # chunk content; untrusted data, never instructions


class Reranker(Protocol):
    name: str

    async def rerank(self, query: str, items: Sequence[RerankItem]) -> list[float]:
        """Return ``len(items)`` finite scores, higher is more relevant."""
        ...


class RerankError(Exception):
    """The reranker failed or returned something unusable; the caller falls back to first-stage order."""
