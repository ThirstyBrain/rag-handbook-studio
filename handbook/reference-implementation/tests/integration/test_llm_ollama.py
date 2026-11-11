"""Integration: the gateway against a REAL local Ollama server (no mocks).

Skipped when Ollama is not reachable. Configure with:
  RAG_TEST_OLLAMA_URL    default http://127.0.0.1:11434/v1
  RAG_TEST_OLLAMA_MODEL  default qwen2.5:0.5b   (any installed chat model; small = fast)
Quality of a 0.5B model is irrelevant here: this verifies the wire protocol, streaming, usage
accounting, error mapping and fallback against a real server.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest

from rag_service.features.llm import (
    ChatRequest,
    EmbedRequest,
    GatewayConfig,
    LlmGateway,
    Message,
    StreamEnd,
    TextDelta,
)
from rag_service.features.llm.gateway import build_providers

pytestmark = pytest.mark.integration
URL = os.environ.get("RAG_TEST_OLLAMA_URL", "http://127.0.0.1:11434/v1")
MODEL = os.environ.get("RAG_TEST_OLLAMA_MODEL", "qwen2.5:0.5b")


def _reachable() -> bool:
    parsed = urlparse(URL)
    try:
        with socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 11434), timeout=1
        ):
            return True
    except OSError:
        return False


requires_ollama = pytest.mark.skipif(not _reachable(), reason=f"Ollama not reachable at {URL}")


def make_gateway() -> LlmGateway:
    cfg = GatewayConfig.model_validate(
        {
            "providers": {
                "dead": {
                    "kind": "openai_compat",
                    "locality": "local",
                    "base_url": "http://127.0.0.1:9/v1",
                },
                "ollama": {"kind": "openai_compat", "locality": "local", "base_url": URL},
                "dev": {"kind": "fake", "locality": "local"},
            },
            "routes": {
                "answer": {
                    "chain": [
                        {"provider": "dead", "model": MODEL},
                        {"provider": "ollama", "model": MODEL},
                    ],
                    "max_attempts_per_target": 1,
                    "timeout_s": 120,
                    "max_output_tokens": 64,
                },
                "embed": {
                    "kind": "embed",
                    "chain": [
                        {"provider": "ollama", "model": MODEL, "embedding_space": "s"},
                        {"provider": "dev", "model": "fake-embed", "embedding_space": "s"},
                    ],
                    "max_attempts_per_target": 1,
                    "timeout_s": 120,
                },
            },
            "backoff": {"base_s": 0.0, "cap_s": 0.0},
        }
    )
    providers, unavailable = build_providers(cfg, env={}, allow_fake=True)
    assert not unavailable
    return LlmGateway(cfg, providers)


REQ = ChatRequest(
    route="answer",
    messages=[Message(role="user", content="Reply with the single word: pong")],
    max_output_tokens=500,  # above the route cap on purpose: the gateway must clamp it to 64
)


@requires_ollama
async def test_real_chat_falls_back_from_dead_endpoint_to_real_server() -> None:
    gw = make_gateway()
    try:
        result = await gw.chat(REQ)
    finally:
        await gw.aclose()
    assert result.provider == "ollama" and result.fallback_used and result.attempts == 2
    assert result.text.strip() != ""
    assert result.usage.input_tokens > 0 and result.usage.output_tokens > 0
    assert result.usage.output_tokens <= 64, "route cap must bound generation"
    assert result.estimated_cost_usd == 0.0


@requires_ollama
async def test_real_streaming_yields_incremental_text_and_usage() -> None:
    gw = make_gateway()
    try:
        events = [e async for e in gw.stream(REQ)]
    finally:
        await gw.aclose()
    deltas = [e.text for e in events if isinstance(e, TextDelta)]
    end = events[-1]
    assert isinstance(end, StreamEnd) and len(deltas) >= 1
    assert "".join(deltas) == end.result.text and end.result.provider == "ollama"
    assert end.result.usage.output_tokens > 0, "stream_options.include_usage must yield usage"


@requires_ollama
async def test_real_embedding_unsupported_model_falls_back_to_next_target_in_same_space() -> None:
    """A chat-only model returns 501 for embeddings; the gateway must fall back, not fail."""
    gw = make_gateway()
    try:
        result = await gw.embed(EmbedRequest(route="embed", inputs=["alpha", "beta"]))
    finally:
        await gw.aclose()
    assert result.provider in {"ollama", "dev"} and result.embedding_space == "s"
    assert len(result.vectors) == 2 and result.dimensions == len(result.vectors[0])
    if result.provider == "dev":
        assert result.fallback_used
