"""OPTIONAL live call to Claude through the gateway. Costs a few tokens; never runs by default.

    export RAG_TEST_LIVE_LLM=1
    export ANTHROPIC_API_KEY=...                 # your key
    export RAG_TEST_ANTHROPIC_MODEL=<a Claude model id you have access to>

It verifies what mocks cannot: that the real API accepts the request the adapter builds, that usage is
reported, and that streaming works end to end. Extend it the same way for other providers.
"""

from __future__ import annotations

import os

import pytest

from rag_service.features.llm import (
    ChatRequest,
    GatewayConfig,
    LlmGateway,
    Message,
    StreamEnd,
    TextDelta,
)
from rag_service.features.llm.gateway import build_providers

pytestmark = pytest.mark.integration
ENABLED = (
    os.environ.get("RAG_TEST_LIVE_LLM") == "1"
    and bool(os.environ.get("ANTHROPIC_API_KEY"))
    and bool(os.environ.get("RAG_TEST_ANTHROPIC_MODEL"))
)
requires_live = pytest.mark.skipif(
    not ENABLED, reason="set RAG_TEST_LIVE_LLM=1, ANTHROPIC_API_KEY and RAG_TEST_ANTHROPIC_MODEL"
)


def make_gateway() -> LlmGateway:
    cfg = GatewayConfig.model_validate(
        {
            "providers": {
                "claude": {
                    "kind": "anthropic",
                    "locality": "external",
                    "api_key_env": "ANTHROPIC_API_KEY",
                }
            },
            "routes": {
                "answer": {
                    "chain": [
                        {"provider": "claude", "model": os.environ["RAG_TEST_ANTHROPIC_MODEL"]}
                    ],
                    "max_attempts_per_target": 1,
                    "timeout_s": 120,
                    # thinking tokens count toward max_tokens, so keep this generous
                    "max_output_tokens": 2000,
                }
            },
        }
    )
    providers, unavailable = build_providers(cfg)
    assert not unavailable
    return LlmGateway(cfg, providers)


REQ = ChatRequest(
    route="answer",
    messages=[Message(role="user", content="Reply with the single word: pong")],
    max_output_tokens=2000,
)


@requires_live
async def test_live_claude_chat_and_stream() -> None:
    gw = make_gateway()
    try:
        result = await gw.chat(REQ)
        assert result.provider == "claude" and result.text.strip() != ""
        assert result.usage.input_tokens > 0 and result.usage.output_tokens > 0
        events = [e async for e in gw.stream(REQ)]
    finally:
        await gw.aclose()
    assert any(isinstance(e, TextDelta) for e in events) and isinstance(events[-1], StreamEnd)
