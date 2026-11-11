"""Reranking (ADR-008): the BM25 baseline, score application, the guard, and the search integration."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest

from rag_service.core.events import LoggingEventSink
from rag_service.db.identity import Identity
from rag_service.features.llm import EmbedRequest, EmbedResult, Usage
from rag_service.features.reranking.apply import apply_scores
from rag_service.features.reranking.guard import GuardedReranker
from rag_service.features.reranking.lexical import Bm25Reranker, tokenize
from rag_service.features.reranking.ports import RerankItem
from rag_service.features.retrieval import service as svc
from rag_service.features.retrieval.fusion import Candidate, FusedHit
from rag_service.features.retrieval.service import HybridSearch, RetrievalConfig


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def cand(n: int, text: str = "") -> Candidate:
    return Candidate(UUID(int=n), UUID(int=1), 1, n, text or f"text {n}", None, None, None, 0.0)


def hit(n: int, text: str = "") -> FusedHit:
    return FusedHit(cand(n, text), 1.0 / n, {"fts": n})


# ------------------------------------------------------------------ BM25 baseline


def test_tokenisation_is_lowercase_alphanumeric() -> None:
    assert tokenize("Leave, 20-days!") == ["leave", "20", "days"]


def test_a_passage_containing_the_rare_query_term_outscores_one_with_only_the_common_term() -> None:
    items = [
        RerankItem("the policy covers leave and expenses"),
        RerankItem("the policy covers expenses"),
        RerankItem("the policy covers travel"),
    ]
    scores = run(Bm25Reranker().rerank("leave policy", items))
    assert scores[0] > scores[1] > 0 and scores[2] > 0


def test_a_passage_with_no_query_term_scores_zero() -> None:
    assert run(Bm25Reranker().rerank("xyz", [RerankItem("alpha beta")])) == [0.0]


def test_shorter_passages_win_at_equal_term_frequency() -> None:
    items = [RerankItem("leave " + "filler " * 40), RerankItem("leave")]
    scores = run(Bm25Reranker().rerank("leave", items))
    assert scores[1] > scores[0]


def test_empty_input_and_invalid_parameters() -> None:
    assert run(Bm25Reranker().rerank("a", [])) == []
    with pytest.raises(ValueError):
        Bm25Reranker(k1=0)
    with pytest.raises(ValueError):
        Bm25Reranker(b=1.5)


# ------------------------------------------------------------------ apply_scores


def test_hits_are_reordered_by_score_and_remember_their_first_stage_position() -> None:
    hits = [hit(1), hit(2), hit(3)]
    out = apply_scores(hits, [0.1, 0.9, 0.5], limit=3)
    assert [h.candidate.ordinal for h in out] == [2, 3, 1]
    assert out[0].score == 0.9 and out[0].ranks["first_stage"] == 2 and out[0].ranks["fts"] == 2


def test_equal_scores_keep_first_stage_order() -> None:
    out = apply_scores([hit(1), hit(2), hit(3)], [0.5, 0.5, 0.5], limit=3)
    assert [h.candidate.ordinal for h in out] == [1, 2, 3]


def test_limit_is_applied_after_reordering() -> None:
    out = apply_scores([hit(1), hit(2), hit(3)], [0.1, 0.2, 0.9], limit=1)
    assert [h.candidate.ordinal for h in out] == [3]


def test_apply_scores_validates_its_inputs() -> None:
    with pytest.raises(ValueError):
        apply_scores([hit(1)], [0.1, 0.2], limit=1)
    with pytest.raises(ValueError):
        apply_scores([hit(1)], [0.1], limit=0)


# ------------------------------------------------------------------ guard


class Scripted:
    name = "scripted"

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def rerank(self, query: str, items: Sequence[RerankItem]) -> list[float]:
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            return await outcome()  # type: ignore[no-any-return]
        return list(outcome)


ITEMS = [RerankItem("a"), RerankItem("b")]


def test_a_healthy_reranker_returns_scores() -> None:
    guard = GuardedReranker(Scripted([0.2, 0.8]), timeout_s=1)
    assert run(guard.rerank("q", ITEMS)) == ([0.2, 0.8], None)


def test_no_items_means_no_call() -> None:
    inner = Scripted([])
    assert run(GuardedReranker(inner, timeout_s=1).rerank("q", [])) == ([], None)
    assert inner.calls == 0


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ([0.1], "rerank:invalid_scores"),
        ([0.1, math.nan], "rerank:invalid_scores"),
        ([0.1, math.inf], "rerank:invalid_scores"),
        (RuntimeError("boom"), "rerank:error"),
    ],
)
def test_malformed_scores_and_errors_fall_back_with_a_reason(outcome: Any, reason: str) -> None:
    result = run(GuardedReranker(Scripted(outcome), timeout_s=1).rerank("q", ITEMS))
    assert result == (None, reason)


def test_a_slow_reranker_times_out() -> None:
    async def slow() -> list[float]:
        await asyncio.sleep(5)
        return [0.0, 0.0]

    result = run(GuardedReranker(Scripted(slow), timeout_s=0.01).rerank("q", ITEMS))
    assert result == (None, "rerank:timeout")


def test_the_breaker_opens_after_repeated_failures_and_recovers_after_the_reset_time() -> None:
    now = [0.0]
    inner = Scripted(RuntimeError("down"), RuntimeError("down"), [0.1, 0.2])
    guard = GuardedReranker(
        inner, timeout_s=1, breaker_threshold=2, breaker_reset_s=30, clock=lambda: now[0]
    )
    assert run(guard.rerank("q", ITEMS))[1] == "rerank:error"
    assert run(guard.rerank("q", ITEMS))[1] == "rerank:error"
    assert run(guard.rerank("q", ITEMS)) == (None, "rerank:circuit_open")
    assert inner.calls == 2, "an open breaker does not call the reranker"
    now[0] = 31.0
    assert run(guard.rerank("q", ITEMS)) == ([0.1, 0.2], None)  # half-open probe succeeds
    assert run(guard.rerank("q", ITEMS)) == ([0.1, 0.2], None)  # closed again


def test_the_guard_rejects_a_nonpositive_timeout() -> None:
    with pytest.raises(ValueError):
        GuardedReranker(Scripted([]), timeout_s=0)


# ------------------------------------------------------------------ integration with hybrid search


class FakeDb:
    async def run(self, identity: Identity, work: Any) -> Any:
        return work(None)


class Gateway:
    async def embed(self, request: EmbedRequest) -> EmbedResult:
        return EmbedResult(
            vectors=[[0.1, 0.2]], usage=Usage(input_tokens=1), provider="f", model="m",
            embedding_space="s", dimensions=2, latency_ms=1.0,
        )  # fmt: skip


@pytest.fixture
def legs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "fts_candidates", lambda *a, **k: [cand(i) for i in range(1, 6)])
    monkeypatch.setattr(svc, "vector_candidates", lambda *a, **k: [])


IDENTITY = Identity(tenant_id=uuid4(), user_id="u", groups=("eng",))


def search_with(inner: Any, **cfg: Any) -> HybridSearch:
    return HybridSearch(
        FakeDb(),  # type: ignore[arg-type]
        Gateway(),
        RetrievalConfig(**cfg),
        LoggingEventSink(),
        reranker=GuardedReranker(inner, timeout_s=1),
    )


def test_reranking_reorders_the_fused_candidates_and_reports_it(legs: None) -> None:
    result = run(search_with(Scripted([0, 0, 0, 0, 9])).search(IDENTITY, "q", top_k=2))
    assert result.reranked is True
    assert result.hits[0].candidate.ordinal == 5 and len(result.hits) == 2
    assert result.hits[0].ranks["first_stage"] == 5


def test_a_failing_reranker_keeps_first_stage_order_and_the_fallback_is_reported(
    legs: None,
) -> None:
    result = run(search_with(Scripted(RuntimeError("x"))).search(IDENTITY, "q", top_k=3))
    assert result.reranked is False and "rerank:error" in result.degraded
    assert [h.candidate.ordinal for h in result.hits] == [1, 2, 3]


def test_the_reranker_sees_n_candidates_not_just_top_k_and_only_retrieved_text(legs: None) -> None:
    seen: list[list[str]] = []

    class Spy:
        name = "spy"

        async def rerank(self, query: str, items: Sequence[RerankItem]) -> list[float]:
            seen.append([i.text for i in items])
            return [0.0] * len(items)

    run(search_with(Spy(), rerank_candidates=4).search(IDENTITY, "q", top_k=2))
    assert seen == [["text 1", "text 2", "text 3", "text 4"]]


def test_without_a_reranker_nothing_changes(legs: None) -> None:
    search = HybridSearch(
        FakeDb(),  # type: ignore[arg-type]
        Gateway(),
        RetrievalConfig(),
        LoggingEventSink(),
    )
    result = run(search.search(IDENTITY, "q", top_k=3))
    assert result.reranked is False and result.degraded == []


def test_bm25_idf_matches_the_standard_formula_on_a_single_document() -> None:
    # n = 1, df = 1: idf = ln(1 + (1 - 1 + 0.5) / (1 + 0.5)) = ln(4/3); tf = 1 and the passage is the average
    # length, so the length factor and (k1 + 1) / (tf + k1) cancel and the score equals the idf.
    (score,) = run(Bm25Reranker().rerank("leave", [RerankItem("leave")]))
    assert score == pytest.approx(math.log(4 / 3))
