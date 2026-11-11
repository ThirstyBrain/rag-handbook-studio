"""Chunk embedding: batching, input recipe, validation of provider output, error mapping (ADR-017)."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest

from rag_service.features.chunking.chunker import Chunk
from rag_service.features.embedding.bridge import AsyncBridge
from rag_service.features.embedding.service import (
    RECIPE,
    ChunkEmbedder,
    EmbeddingConfig,
    EmbeddingError,
    embedding_input,
)
from rag_service.features.extraction.model import Rejected
from rag_service.features.llm import (
    ContentRefused,
    EmbedRequest,
    EmbedResult,
    GatewayConfig,
    InvalidRequest,
    Usage,
    build_gateway,
)
from rag_service.features.llm.config import ProviderConfig, RouteConfig, Target
from rag_service.features.llm.errors import ProviderUnavailable
from rag_service.features.llm.providers.fake import FAKE_DIMENSIONS

T = TypeVar("T")


class InlineRunner:
    """TEST DOUBLE for the async bridge: runs the coroutine to completion on a fresh loop."""

    def run(self, coro: Coroutine[Any, Any, T], timeout_s: float) -> T:
        return asyncio.run(asyncio.wait_for(coro, timeout_s))


def chunk(ordinal: int, content: str = "alpha", path: str = "") -> Chunk:
    return Chunk(ordinal, content, path, 1, None, None)


def result(
    vectors: list[list[float]], *, space: str = "s1", model: str = "m1", dims: int | None = None
) -> EmbedResult:
    return EmbedResult(
        vectors=vectors,
        usage=Usage(input_tokens=len(vectors)),
        provider="p",
        model=model,
        embedding_space=space,
        dimensions=dims if dims is not None else len(vectors[0]),
        latency_ms=0.0,
    )


class ScriptedGateway:
    """Answers each embed call with the next scripted outcome, or a deterministic vector per input."""

    def __init__(self, *outcomes: EmbedResult | Exception) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[EmbedRequest] = []

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        self.requests.append(request)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return result([[float(len(t)), 1.0, 0.5] for t in request.inputs])


def embedder(gateway: ScriptedGateway, **kw: Any) -> ChunkEmbedder:
    return ChunkEmbedder(gateway, EmbeddingConfig(**kw), InlineRunner())


# ------------------------------------------------------------------ recipe and batching


def test_the_section_path_is_embedded_with_the_content() -> None:
    assert embedding_input(chunk(0, "Twenty days.", "Handbook > Leave")) == (
        "Handbook > Leave\n\nTwenty days."
    )
    assert embedding_input(chunk(0, "Twenty days.", "")) == "Twenty days."


def test_chunks_are_embedded_in_order_in_batches_of_the_configured_size() -> None:
    gateway = ScriptedGateway()
    chunks = [chunk(i, "x" * (i + 1)) for i in range(70)]
    out = embedder(gateway, batch_size=32).embed(chunks)
    assert [len(r.inputs) for r in gateway.requests] == [32, 32, 6]
    assert out.calls == 3 and len(out.vectors) == 70 and len(out.models) == 70
    assert [v[0] for v in out.vectors] == [float(i + 1) for i in range(70)], "order preserved"
    assert out.recipe == RECIPE and out.space == "s1" and out.dimensions == 3
    assert out.input_tokens == 70


def test_the_request_names_the_route_and_carries_the_sensitivity() -> None:
    from rag_service.features.llm import Sensitivity

    gateway = ScriptedGateway()
    embedder(gateway, route="embed-private", sensitivity=Sensitivity.RESTRICTED).embed([chunk(0)])
    assert gateway.requests[0].route == "embed-private"
    assert gateway.requests[0].sensitivity is Sensitivity.RESTRICTED


def test_nothing_to_embed_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        embedder(ScriptedGateway()).embed([])


def test_the_model_is_recorded_per_chunk_when_a_fallback_changes_it() -> None:
    gateway = ScriptedGateway(
        result([[1.0, 0.0]], model="primary"),
        EmbedResult(**{**result([[0.0, 1.0]], model="backup").model_dump(), "fallback_used": True}),
    )
    out = embedder(gateway, batch_size=1).embed([chunk(0), chunk(1)])
    assert out.models == ["primary", "backup"] and out.fallback_used is True


# ------------------------------------------------------------------ provider output is untrusted


@pytest.mark.parametrize(
    ("bad", "why"),
    [
        (result([[1.0, 0.0]]), "wrong number of vectors"),
        (result([[1.0, 0.0], [float("nan"), 1.0]]), "non-finite"),
        (result([[1.0, 0.0], [float("inf"), 1.0]]), "non-finite"),
        (result([[1.0, 0.0], [0.0, 0.0]]), "zero vector"),
        (result([[1.0, 0.0], [1.0, 0.0]], space=""), "no embedding_space"),
        (result([[1.0, 0.0], [1.0, 0.0]], dims=5), "dimension"),
        (result([[1.0, 0.0], [1.0]], dims=2), "mismatch"),
    ],
)
def test_unstorable_provider_output_is_rejected(bad: EmbedResult, why: str) -> None:
    with pytest.raises(EmbeddingError, match=why.split()[0]):
        embedder(ScriptedGateway(bad)).embed([chunk(0), chunk(1)])


def test_dimensions_above_the_supported_maximum_are_rejected() -> None:
    wide = result([[1.0] * 9, [1.0] * 9])
    with pytest.raises(EmbeddingError, match="dimension"):
        embedder(ScriptedGateway(wide), max_dimensions=8).embed([chunk(0), chunk(1)])


def test_a_space_or_dimension_change_between_batches_is_rejected() -> None:
    with pytest.raises(EmbeddingError, match="space changed"):
        embedder(
            ScriptedGateway(result([[1.0, 0.0]], space="a"), result([[1.0, 0.0]], space="b")),
            batch_size=1,
        ).embed([chunk(0), chunk(1)])
    with pytest.raises(EmbeddingError, match="space changed"):
        embedder(
            ScriptedGateway(result([[1.0, 0.0]]), result([[1.0, 0.0, 0.0]])), batch_size=1
        ).embed([chunk(0), chunk(1)])


# ------------------------------------------------------------------ errors


@pytest.mark.parametrize("error", [InvalidRequest("too long"), ContentRefused("no")])
def test_inputs_that_will_always_be_refused_end_the_job_permanently(error: Exception) -> None:
    with pytest.raises(Rejected) as info:
        embedder(ScriptedGateway(error)).embed([chunk(0)])
    assert info.value.reason == "embedding_rejected"


def test_outages_propagate_so_the_job_is_retried() -> None:
    with pytest.raises(ProviderUnavailable):
        embedder(ScriptedGateway(ProviderUnavailable("down"))).embed([chunk(0)])


def test_a_call_that_exceeds_the_timeout_propagates() -> None:
    class Slow:
        async def embed(self, request: EmbedRequest) -> EmbedResult:
            await asyncio.sleep(5)
            raise AssertionError("unreachable")

    with pytest.raises(TimeoutError):
        ChunkEmbedder(Slow(), EmbeddingConfig(call_timeout_s=0.05), InlineRunner()).embed(
            [chunk(0)]
        )


@pytest.mark.parametrize(
    "kw",
    [{"batch_size": 0}, {"max_dimensions": 0}, {"max_dimensions": 4001}, {"call_timeout_s": 0}],
)
def test_invalid_configuration_is_refused(kw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        EmbeddingConfig(**kw)


# ------------------------------------------------------------------ the real gateway and the fake provider


def test_with_the_real_gateway_and_the_fake_provider_vectors_are_deterministic() -> None:
    config = GatewayConfig(
        providers={"f": ProviderConfig(kind="fake", locality="local")},
        routes={
            "embed": RouteConfig(
                kind="embed", chain=[Target(provider="f", model="m", embedding_space="fake-v1")]
            )
        },
    )
    gateway = build_gateway(config, allow_fake=True)
    with_bridge = AsyncBridge()
    try:
        emb = ChunkEmbedder(gateway, EmbeddingConfig(batch_size=2), with_bridge)
        first = emb.embed([chunk(0, "a"), chunk(1, "b"), chunk(2, "c")])
        second = emb.embed([chunk(0, "a"), chunk(1, "b"), chunk(2, "c")])
    finally:
        with_bridge.run(gateway.aclose(), 5)
        with_bridge.close()
    assert first.vectors == second.vectors and first.dimensions == FAKE_DIMENSIONS
    assert first.space == "fake-v1" and first.calls == 2
    assert first.vectors[0] != first.vectors[1]


# ------------------------------------------------------------------ the async bridge


def test_the_bridge_runs_every_call_on_one_loop_thread() -> None:
    bridge = AsyncBridge()
    try:

        async def where() -> int:
            return threading.get_ident()

        first, second = bridge.run(where(), 5), bridge.run(where(), 5)
        assert first == second != threading.get_ident()
    finally:
        bridge.close()


def test_the_bridge_times_out_and_cancels_the_coroutine() -> None:
    bridge = AsyncBridge()
    cancelled = threading.Event()

    async def slow() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    try:
        with pytest.raises(TimeoutError):
            bridge.run(slow(), 0.05)
        deadline = time.monotonic() + 2
        while not cancelled.is_set() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert cancelled.is_set()
    finally:
        bridge.close()


def test_the_bridge_propagates_exceptions() -> None:
    bridge = AsyncBridge()

    async def boom() -> None:
        raise ProviderUnavailable("x")

    try:
        with pytest.raises(ProviderUnavailable):
            bridge.run(boom(), 5)
    finally:
        bridge.close()


# ------------------------------------------------------------------ worker start-up policy


def test_the_worker_refuses_to_start_with_embedding_enabled_and_no_gateway(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from rag_service.jobs import worker

    monkeypatch.setenv("RAG_WORKER_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
    monkeypatch.setenv("RAG_EMBEDDING_ENABLED", "true")
    monkeypatch.delenv("RAG_LLM_CONFIG_FILE", raising=False)
    assert worker.main() == 2
    assert "RAG_LLM_CONFIG_FILE" in capsys.readouterr().out


# ------------------------------------------------------------------ derived chunk identity


def test_chunk_ids_are_stable_and_depend_on_every_input() -> None:
    from uuid import uuid4

    from rag_service.features.ingestion.chunk_store import chunk_id_for

    t, d = uuid4(), uuid4()
    base = chunk_id_for(t, d, 1, chunk(0, "same text"))
    assert base == chunk_id_for(t, d, 1, chunk(0, "same text")), "stable across re-processing"
    assert base != chunk_id_for(t, d, 1, chunk(0, "other text")), "content"
    assert base != chunk_id_for(t, d, 1, chunk(1, "same text")), "position"
    assert base != chunk_id_for(t, d, 2, chunk(0, "same text")), "version"
    assert base != chunk_id_for(t, uuid4(), 1, chunk(0, "same text")), "document"
    assert base != chunk_id_for(uuid4(), d, 1, chunk(0, "same text")), "tenant"
