"""Provider adapters against mocked HTTP transports: request shape, response parsing, error mapping."""

from __future__ import annotations

import json
from collections.abc import Callable

import anthropic
import httpx
import httpx2
import pytest

from rag_service.features.llm import ChatRequest, Message, StreamEnd, TextDelta
from rag_service.features.llm.errors import (
    ContentRefused,
    InvalidRequest,
    ProviderAuthError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
    TargetUnsupported,
)
from rag_service.features.llm.providers.anthropic import AnthropicProvider
from rag_service.features.llm.providers.openai_compat import OpenAICompatProvider

SECRET = "SECRET-PROMPT-TEXT-42"
REQ = ChatRequest(
    route="answer",
    system="be brief",
    messages=[Message(role="user", content=SECRET)],
    max_output_tokens=50,
    temperature=0.3,
    stop=["END"],
)

# ============================================================ OpenAI-compatible (OpenAI, Grok, Ollama...)


def oa_provider(
    handler: Callable[[httpx.Request], httpx.Response], **kw: object
) -> OpenAICompatProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://llm.test/v1"
    )
    return OpenAICompatProvider(
        "p", base_url="http://llm.test/v1", locality="local", http_client=client, **kw
    )  # type: ignore[arg-type]


def ok_chat(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "prompt_tokens_details": {"cached_tokens": 2},
            },
        },
    )


async def test_openai_compat_request_shape_and_parse() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return ok_chat(request)

    result = await oa_provider(handler).chat("m1", REQ)
    body = seen["body"]
    assert seen["path"] == "/v1/chat/completions"
    assert isinstance(body, dict)
    assert (
        body["model"] == "m1"
        and body["max_tokens"] == 50
        and body["temperature"] == 0.3
        and body["stop"] == ["END"]
    )
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": SECRET} and body["stream"] is False
    assert result.text == "hello" and result.finish_reason == "stop"
    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cached_input_tokens,
    ) == (7, 3, 2)


async def test_openai_compat_uses_configured_max_tokens_param_and_bearer_key() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return ok_chat(request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://llm.test/v1",
        headers={"Authorization": "Bearer k-123"},
    )
    provider = OpenAICompatProvider(
        "p",
        base_url="http://llm.test/v1",
        locality="external",
        api_key="k-123",
        max_tokens_param="max_completion_tokens",
        http_client=client,
    )
    await provider.chat("m", REQ)
    body = seen["body"]
    assert isinstance(body, dict) and "max_completion_tokens" in body and "max_tokens" not in body
    assert seen["auth"] == "Bearer k-123"


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (429, {"retry-after": "2"}, RateLimited),
        (401, {}, ProviderAuthError),
        (403, {}, ProviderAuthError),
        (408, {}, ProviderTimeout),
        (500, {}, ProviderUnavailable),
        (503, {}, ProviderUnavailable),
        (400, {}, InvalidRequest),
        (404, {}, TargetUnsupported),
        (501, {}, TargetUnsupported),
    ],
)
async def test_openai_compat_status_mapping_never_echoes_body(
    status: int, headers: dict[str, str], expected: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status, headers=headers, json={"error": {"message": f"echo {SECRET}"}}
        )

    with pytest.raises(expected) as info:
        await oa_provider(handler).chat("m", REQ)
    assert SECRET not in str(info.value)
    if expected is RateLimited:
        assert info.value.retry_after_s == 2.0  # type: ignore[attr-defined]


async def test_openai_compat_transport_errors_and_malformed_body() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(ProviderTimeout):
        await oa_provider(timeout).chat("m", REQ)
    with pytest.raises(ProviderUnavailable):
        await oa_provider(refused).chat("m", REQ)
    with pytest.raises(ProviderUnavailable):
        await oa_provider(lambda r: httpx.Response(200, content=b"<html>not json</html>")).chat(
            "m", REQ
        )
    with pytest.raises(ProviderUnavailable):
        await oa_provider(lambda r: httpx.Response(200, json={"choices": []})).chat("m", REQ)


async def test_openai_compat_content_filter_maps_to_refusal_and_length() -> None:
    def make(reason: str) -> Callable[[httpx.Request], httpx.Response]:
        return lambda r: httpx.Response(
            200,
            json={"choices": [{"message": {"content": ""}, "finish_reason": reason}], "usage": {}},
        )

    assert (await oa_provider(make("content_filter")).chat("m", REQ)).finish_reason == "refusal"
    assert (await oa_provider(make("length")).chat("m", REQ)).finish_reason == "length"
    assert (await oa_provider(make("weird")).chat("m", REQ)).finish_reason == "other"


async def test_openai_compat_streaming_sse() -> None:
    seen: dict[str, object] = {}
    chunks = [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 2}},
    ]
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, content=sse.encode(), headers={"content-type": "text/event-stream"}
        )

    events = [e async for e in oa_provider(handler).stream("m", REQ)]
    body = seen["body"]
    assert (
        isinstance(body, dict)
        and body["stream"] is True
        and body["stream_options"] == {"include_usage": True}
    )
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hel", "lo"]
    end = events[-1]
    assert (
        isinstance(end, StreamEnd)
        and end.result.text == "Hello"
        and end.result.finish_reason == "stop"
    )
    assert (end.result.usage.input_tokens, end.result.usage.output_tokens) == (4, 2)


async def test_openai_compat_stream_http_error_is_mapped() -> None:
    with pytest.raises(RateLimited):
        async for _ in oa_provider(lambda r: httpx.Response(429, json={"error": "x"})).stream(
            "m", REQ
        ):
            pass


async def test_openai_compat_embeddings_are_ordered_and_counted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings" and json.loads(request.content)["input"] == [
            "a",
            "b",
        ]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ],
                "usage": {"prompt_tokens": 2},
            },
        )

    vectors, usage = await oa_provider(handler).embed("e", ["a", "b"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]] and usage.input_tokens == 2
    with pytest.raises(ProviderUnavailable):  # count mismatch
        await oa_provider(
            lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})
        ).embed("e", ["a", "b"])


# ============================================================ Anthropic (official SDK)

MESSAGE_OK = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-test",
    "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 4},
}


def an_provider(handler: Callable[[httpx2.Request], httpx2.Response]) -> AnthropicProvider:
    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        base_url="http://anthropic.test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider("claude", api_key="test-key", client=client)


async def test_anthropic_request_shape_and_parse() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get(
            "authorization"
        )  # anthropic 2.6.0 sends the key as a bearer token
        seen["version"] = request.headers.get("anthropic-version")
        return httpx2.Response(200, json=MESSAGE_OK)

    result = await an_provider(handler).chat("claude-test", REQ)
    body = seen["body"]
    assert isinstance(body, dict)
    assert seen["path"] == "/v1/messages" and seen["key"] == "Bearer test-key" and seen["version"]
    assert (
        body["model"] == "claude-test" and body["max_tokens"] == 50 and body["system"] == "be brief"
    )
    assert body["stop_sequences"] == ["END"] and body["messages"] == [
        {"role": "user", "content": SECRET}
    ]
    assert "temperature" not in body, "current Claude models reject temperature"
    assert (
        result.text == "Hello world"
        and result.finish_reason == "stop"
        and result.provider == "claude"
    )
    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cached_input_tokens,
    ) == (10, 5, 4)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [("max_tokens", "length"), ("stop_sequence", "stop"), ("tool_use", "other")],
)
async def test_anthropic_stop_reason_mapping(reason: str, expected: str) -> None:
    payload = {**MESSAGE_OK, "stop_reason": reason}
    result = await an_provider(lambda r: httpx2.Response(200, json=payload)).chat("m", REQ)
    assert result.finish_reason == expected


async def test_anthropic_refusal_becomes_content_refused() -> None:
    payload = {**MESSAGE_OK, "stop_reason": "refusal", "content": []}
    with pytest.raises(ContentRefused):
        await an_provider(lambda r: httpx2.Response(200, json=payload)).chat("m", REQ)


@pytest.mark.parametrize(
    ("status", "error_type", "expected"),
    [
        (429, "rate_limit_error", RateLimited),
        (529, "overloaded_error", ProviderUnavailable),
        (500, "api_error", ProviderUnavailable),
        (401, "authentication_error", ProviderAuthError),
        (403, "permission_error", ProviderAuthError),
        (400, "invalid_request_error", InvalidRequest),
        (404, "not_found_error", TargetUnsupported),
    ],
)
async def test_anthropic_error_mapping_and_no_sdk_retries(
    status: int, error_type: str, expected: type[Exception]
) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        return httpx2.Response(
            status,
            headers={"retry-after": "3"} if status == 429 else {},
            json={"type": "error", "error": {"type": error_type, "message": f"echo {SECRET}"}},
        )

    with pytest.raises(expected) as info:
        await an_provider(handler).chat("m", REQ)
    assert calls["n"] == 1, "the gateway owns retries; the SDK must not retry"
    assert SECRET not in str(info.value)
    if expected is RateLimited:
        assert info.value.retry_after_s == 3.0  # type: ignore[attr-defined]


async def test_anthropic_connection_and_timeout_errors() -> None:
    def refused(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderUnavailable):
        await an_provider(refused).chat("m", REQ)
    with pytest.raises(ProviderTimeout):
        await an_provider(slow).chat("m", REQ)


async def test_anthropic_streaming() -> None:
    def sse(event: str, data: dict[str, object]) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    body = "".join(
        [
            sse(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        **MESSAGE_OK,
                        "content": [],
                        "stop_reason": None,
                        "usage": {"input_tokens": 9, "output_tokens": 1},
                    },
                },
            ),
            sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Hel"},
                },
            ),
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "lo"},
                },
            ),
            sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
            sse(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 6},
                },
            ),
            sse("message_stop", {"type": "message_stop"}),
        ]
    )
    seen: dict[str, object] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200, content=body.encode(), headers={"content-type": "text/event-stream"}
        )

    events = [e async for e in an_provider(handler).stream("claude-test", REQ)]
    assert isinstance(seen["body"], dict) and seen["body"]["stream"] is True
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hel", "lo"]
    end = events[-1]
    assert (
        isinstance(end, StreamEnd)
        and end.result.text == "Hello"
        and end.result.finish_reason == "stop"
    )
    assert end.result.usage.output_tokens == 6


async def test_anthropic_has_no_embeddings() -> None:
    with pytest.raises(InvalidRequest):
        await an_provider(lambda r: httpx2.Response(200, json=MESSAGE_OK)).embed("m", ["x"])
