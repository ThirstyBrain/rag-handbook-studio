"""Reciprocal rank fusion (ADR-004): combine ranked candidate lists without calibrating their scores.

Full-text and vector scores live on incomparable scales, so only RANKS are used:
``score(d) = sum over legs of weight_leg / (k + rank_leg(d))`` with 1-based ranks. ``k`` damps the
influence of the very top ranks; 60 is the constant used in the original RRF paper (to be tuned by the
golden set, component 17). Pure and deterministic: ties break on the chunk id, so a result never
depends on dict or database ordering.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Candidate:
    """One chunk returned by one retrieval leg."""

    chunk_id: UUID
    document_id: UUID
    version: int
    ordinal: int
    content: str
    section_path: str | None
    page_start: int | None
    page_end: int | None
    raw_score: float  # the leg's own score (ts_rank_cd, or cosine distance); informational only


@dataclass(frozen=True)
class FusedHit:
    candidate: Candidate
    score: float
    ranks: Mapping[str, int] = field(default_factory=dict)  # leg name -> 1-based rank


def reciprocal_rank_fusion(
    legs: Mapping[str, Sequence[Candidate]],
    *,
    k: int = 60,
    weights: Mapping[str, float] | None = None,
    limit: int = 10,
) -> list[FusedHit]:
    """Fuse ranked lists (best first). A chunk appearing twice in one leg keeps its best rank."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    weights = weights or {}
    scores: dict[UUID, float] = {}
    ranks: dict[UUID, dict[str, int]] = {}
    best: dict[UUID, Candidate] = {}
    for name, candidates in legs.items():
        weight = weights.get(name, 1.0)
        if weight < 0:
            raise ValueError("leg weights must not be negative")
        for position, candidate in enumerate(candidates, start=1):
            seen = ranks.setdefault(candidate.chunk_id, {})
            if name in seen:
                continue  # duplicate within a leg: the first (best) rank counts
            seen[name] = position
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + weight / (
                k + position
            )
            best.setdefault(candidate.chunk_id, candidate)
    ordered = sorted(scores, key=lambda cid: (-scores[cid], str(cid)))
    return [FusedHit(best[cid], scores[cid], dict(ranks[cid])) for cid in ordered[:limit]]
