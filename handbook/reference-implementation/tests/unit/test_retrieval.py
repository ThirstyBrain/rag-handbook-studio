"""Hybrid retrieval without a database: RRF fusion, query validation, and the service's degradation logic.

The SQL of the two legs is exercised only by the integration tests (tests/integration/test_retrieval_db.py),
which need PostgreSQL with pgvector. Here the legs are replaced by in-memory fakes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest

from rag_service.core.events import LoggingEventSink
from rag_service.db.identity import Identity
from rag_service.features.indexing.ddl import VectorIndexSpec
from rag_service.features.llm import EmbedRequest, EmbedResult, Usage
from rag_service.features.llm.errors import ProviderUnavailable
from rag_service.features.retrieval import service as svc
from rag_service.features.retrieval.fusion import Candidate, reciprocal_rank_fusion
from rag_service.features.retrieval.query import (
    MAX_QUERY_CHARS,
    QueryError,
    normalise_query,
    validate_query_vector,
)
from rag_service.features.retrieval.service import HybridSearch, RetrievalConfig


def cand(n: int, score: float = 0.0) -> Candidate:
    return Candidate(UUID(int=n), UUID(int=1), 1, n, f"text {n}", None, None, None, score)


# ------------------------------------------------------------------ fusion


def test_a_chunk_found_by_both_legs_outranks_chunks_found_by_one() -> None:
    hits = reciprocal_rank_fusion({"fts": [cand(1), cand(2)], "vector": [cand(3), cand(2)]})
    assert hits[0].candidate.ordinal == 2
    assert hits[0].ranks == {"fts": 2, "vector": 2}


def test_rrf_score_is_the_sum_of_weight_over_k_plus_rank() -> None:
    hits = reciprocal_rank_fusion({"fts": [cand(1)], "vector": [cand(1)]}, k=60)
    assert hits[0].score == pytest.approx(2 / 61)


def test_weights_change_the_ordering() -> None:
    legs = {"fts": [cand(1)], "vector": [cand(2)]}
    heavy_fts = reciprocal_rank_fusion(legs, weights={"fts": 2.0, "vector": 1.0})
    heavy_vec = reciprocal_rank_fusion(legs, weights={"fts": 1.0, "vector": 2.0})
    assert heavy_fts[0].candidate.ordinal == 1 and heavy_vec[0].candidate.ordinal == 2


def test_ties_break_on_chunk_id_so_the_order_is_deterministic() -> None:
    a = reciprocal_rank_fusion({"fts": [cand(2)], "vector": [cand(1)]})
    b = reciprocal_rank_fusion({"vector": [cand(1)], "fts": [cand(2)]})
    assert [h.candidate.chunk_id for h in a] == [h.candidate.chunk_id for h in b]
    assert a[0].candidate.ordinal == 1


def test_a_duplicate_within_a_leg_counts_once_at_its_best_rank() -> None:
    hits = reciprocal_rank_fusion({"fts": [cand(1), cand(1)]}, k=60)
    assert len(hits) == 1 and hits[0].score == pytest.approx(1 / 61)


def test_limit_and_empty_input() -> None:
    assert reciprocal_rank_fusion({}) == []
    assert len(reciprocal_rank_fusion({"fts": [cand(i) for i in range(1, 9)]}, limit=3)) == 3


@pytest.mark.parametrize("kwargs", [{"k": 0}, {"limit": 0}, {"weights": {"fts": -1.0}}])
def test_invalid_fusion_parameters_are_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({"fts": [cand(1)]}, **kwargs)


# ------------------------------------------------------------------ query validation


def test_query_is_trimmed_and_whitespace_collapsed() -> None:
    assert normalise_query("  how   many\n days  ") == "how many days"


@pytest.mark.parametrize("bad", ["", "   \n\t", "a\x00b", "x" * (MAX_QUERY_CHARS + 1)])
def test_bad_queries_are_rejected(bad: str) -> None:
    with pytest.raises(QueryError):
        normalise_query(bad)


@pytest.mark.parametrize(
    "vector",
    [[0.0, 0.0, 0.0], [1.0, float("nan"), 0.0], [1.0, float("inf"), 0.0], [1.0, 2.0]],
)
def test_bad_query_vectors_are_rejected(vector: list[float]) -> None:
    with pytest.raises(QueryError):
        validate_query_vector(vector, 3, 4000)


def test_a_good_query_vector_passes_and_the_dimension_cap_applies() -> None:
    validate_query_vector([0.1, 0.2, 0.3], 3, 4000)
    with pytest.raises(QueryError):
        validate_query_vector([0.1, 0.2, 0.3], 3, 2)


# ------------------------------------------------------------------ service


class FakeDb:
    def __init__(self) -> None:
        self.identities: list[Identity] = []

    async def run(self, identity: Identity, work: Callable[[Any], Any]) -> Any:
        self.identities.append(identity)
        return work(None)


class FakeGateway:
    def __init__(self, vector: list[float] | None = None, error: Exception | None = None) -> None:
        self.vector, self.error, self.requests = vector, error, []

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        self.requests.append(request)
        if self.error:
            raise self.error
        assert self.vector is not None
        return EmbedResult(
            vectors=[self.vector], usage=Usage(input_tokens=1), provider="f", model="m",
            embedding_space="fake-v1", dimensions=len(self.vector), latency_ms=1.0,
        )  # fmt: skip


class Events:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict[str, Any]]] = []

    def emit(self, name: str, props: Any = None) -> None:
        self.emitted.append((name, dict(props or {})))


@pytest.fixture
def legs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fts(conn: Any, query: str, limit: int, flt: Any = None) -> list[Candidate]:
        seen["fts_query"], seen["fts_flt"] = query, flt
        return [cand(1), cand(2)]

    def vec(
        conn: Any, spec: VectorIndexSpec, vector: Any, limit: int, **kw: Any
    ) -> list[Candidate]:
        seen["spec"], seen["vector_kw"], seen["vec_flt"] = spec, kw, kw.get("flt")
        return [cand(2), cand(3)]

    monkeypatch.setattr(svc, "fts_candidates", fts)
    monkeypatch.setattr(svc, "vector_candidates", vec)
    return seen


IDENTITY = Identity(tenant_id=uuid4(), user_id="u", groups=("eng",))


def make(gateway: Any, events: Any = None, **cfg: Any) -> tuple[HybridSearch, FakeDb]:
    db = FakeDb()
    return HybridSearch(db, gateway, RetrievalConfig(**cfg), events or LoggingEventSink()), db  # type: ignore[arg-type]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_both_legs_run_and_are_fused(legs: dict[str, Any]) -> None:
    search, db = make(FakeGateway([0.1, 0.2, 0.3]))
    result = run(search.search(IDENTITY, "  leave   policy ", top_k=2))
    assert result.legs_used == ["fts", "vector"] and result.degraded == []
    assert legs["fts_query"] == "leave policy"
    assert legs["spec"] == VectorIndexSpec("fake-v1", 3)
    assert result.hits[0].candidate.ordinal == 2 and len(result.hits) == 2
    assert result.candidates == {"fts": 2, "vector": 2}
    assert db.identities == [IDENTITY], "the caller's identity scopes the transaction"


def test_without_a_gateway_the_lexical_leg_answers_and_degradation_is_reported(
    legs: dict[str, Any],
) -> None:
    result = run(make(None)[0].search(IDENTITY, "leave"))
    assert result.legs_used == ["fts"] and result.degraded == ["vector:not_configured"]
    assert "spec" not in legs


def test_a_provider_outage_degrades_to_lexical_only(legs: dict[str, Any]) -> None:
    result = run(make(FakeGateway(error=ProviderUnavailable("down")))[0].search(IDENTITY, "leave"))
    assert result.legs_used == ["fts"] and result.degraded == ["vector:provider_error"]


def test_a_slow_embedding_call_times_out_and_degrades(legs: dict[str, Any]) -> None:
    class Slow:
        async def embed(self, request: EmbedRequest) -> EmbedResult:
            await asyncio.sleep(5)
            raise AssertionError("unreachable")

    result = run(make(Slow(), embed_timeout_s=0.01)[0].search(IDENTITY, "leave"))
    assert result.degraded == ["vector:timeout"]


def test_an_invalid_query_embedding_is_not_used(legs: dict[str, Any]) -> None:
    result = run(make(FakeGateway([0.0, 0.0, 0.0]))[0].search(IDENTITY, "leave"))
    assert result.legs_used == ["fts"] and result.degraded == ["vector:invalid_embedding"]


def test_top_k_is_bounded_and_the_query_validated(legs: dict[str, Any]) -> None:
    search, _ = make(FakeGateway([0.1]), candidates_per_leg=10, max_top_k=5)
    with pytest.raises(QueryError):
        run(search.search(IDENTITY, "leave", top_k=6))
    with pytest.raises(QueryError):
        run(search.search(IDENTITY, "   ", top_k=1))


def test_events_carry_counts_never_the_query_text(legs: dict[str, Any]) -> None:
    events = Events()
    run(make(FakeGateway([0.1, 0.2]), events)[0].search(IDENTITY, "secret salary question"))
    ((name, props),) = events.emitted
    assert name == "search_completed" and props["legs"] == "fts+vector"
    assert "secret" not in repr(props)


def test_config_rejects_inconsistent_limits() -> None:
    with pytest.raises(ValueError):
        RetrievalConfig(candidates_per_leg=10, max_top_k=11)


def test_filters_compile_once_and_reach_both_legs_and_bad_filters_fail_before_embedding(
    legs: dict[str, Any],
) -> None:
    from rag_service.features.retrieval.filters import Condition, FilterError

    gateway = FakeGateway([0.1, 0.2, 0.3])
    search, _ = make(gateway)
    cond = Condition(field="source_id", op="prefix", value="hr/")
    run(search.search(IDENTITY, "leave", filters=[cond]))
    assert legs["fts_flt"].params == ("hr/",) and legs["vec_flt"] is legs["fts_flt"]
    assert len(gateway.requests) == 1

    gateway2 = FakeGateway([0.1, 0.2, 0.3])
    bad = Condition(field="document_id", op="eq", value="nope")
    with pytest.raises(FilterError):
        run(make(gateway2)[0].search(IDENTITY, "leave", filters=[bad]))
    assert gateway2.requests == [], "no embedding call is paid for an invalid filter"


def test_a_provider_returning_the_wrong_number_of_query_vectors_is_not_used(
    legs: dict[str, Any],
) -> None:
    class Two(FakeGateway):
        async def embed(self, request: EmbedRequest) -> EmbedResult:
            one = await super().embed(request)
            return one.model_copy(update={"vectors": [*one.vectors, *one.vectors]})

    result = run(make(Two([0.1, 0.2, 0.3]))[0].search(IDENTITY, "leave"))
    assert result.legs_used == ["fts"] and result.degraded == ["vector:invalid_embedding"]
