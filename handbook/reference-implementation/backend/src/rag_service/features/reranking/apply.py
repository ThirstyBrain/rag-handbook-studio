"""Apply reranker scores to fused hits: pure, deterministic, order-preserving on ties."""

from __future__ import annotations

from collections.abc import Sequence

from rag_service.features.retrieval.fusion import FusedHit


def apply_scores(hits: Sequence[FusedHit], scores: Sequence[float], limit: int) -> list[FusedHit]:
    """Reorder ``hits`` by descending reranker score and keep ``limit``.

    Ties keep first-stage order (stable), so a reranker that scores everything equally changes nothing. The
    returned hit's ``score`` is the reranker score (meaningful only within this result) and ``ranks`` gains
    ``first_stage`` (the 1-based fused position) so the movement is visible to evaluation and debugging."""
    if len(hits) != len(scores):
        raise ValueError("one score per hit is required")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    order = sorted(range(len(hits)), key=lambda i: (-scores[i], i))
    return [
        FusedHit(
            candidate=hits[i].candidate,
            score=scores[i],
            ranks={**hits[i].ranks, "first_stage": i + 1},
        )
        for i in order[:limit]
    ]
