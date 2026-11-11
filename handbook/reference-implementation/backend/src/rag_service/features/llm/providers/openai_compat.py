"""Adapter for servers that speak the OpenAI Chat Completions / Embeddings wire format.

Used for OpenAI, xAI Grok, Ollama (local, ``/v1``), vLLM and similar. Plain ``httpx``: no vendor SDK.
Wire format facts used here were checked against the Ollama OpenAI-compatibility documentation and by
running against a local Ollama server; OpenAI's and xAI's own reference pages could not be read
(HTTP 403 and Responses-only respectively), so those two are *unverified against vendor docs*.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from rag_service.features.llm.errors import (
    InvalidRequest,
    LlmError,
    ProviderAuthError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
    TargetUnsupported,
)
from rag_service.features.llm.ports import Locality
from rag_service.features.llm.types import (
    ChatRequest,
    ChatResult,
    FinishReason,
    StreamEnd,
    StreamEvent,
    TextDelta,
    Usage,
)

_FINISH: dict[str, FinishReason] = {"stop": "stop", "length": "length", "content_filter": "refusal"}
_CONNECT_TIMEOUT_S = 5.0
_CLIENT_TIMEOUT_S = 600.0  # upper bound only; the gateway enforces the route timeout


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def _raise_for_status(response: httpx.Response, provider: str) -> None:
    status = response.status_code
    if status < 400:
        return
    if status == 429:
        raise RateLimited("rate limited", provider=provider, retry_after_s=_retry_after(response))
    if status in (401, 403):
        raise ProviderAuthError("credentials rejected", provider=provider)
    if status == 408:
        raise ProviderTimeout("provider timed out", provider=provider)
    if status in (
        404,
        501,
    ):  # unknown model/endpoint, or the model cannot do this (e.g. no embeddings)
        raise TargetUnsupported(
            f"target does not support this request ({status})", provider=provider
        )
    if status >= 500:
        raise ProviderUnavailable("provider error", provider=provider)
    raise InvalidRequest(f"request rejected with status {status}", provider=provider)


def _map_transport_error(exc: Exception, provider: str) -> LlmError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeout("provider timed out", provider=provider)
    return ProviderUnavailable("provider unreachable", provider=provider)


def _usage(payload: dict[str, Any] | None) -> Usage:
    if not payload:
        return Usage()
    details = payload.get("prompt_tokens_details") or {}
    return Usage(
        input_tokens=int(payload.get("prompt_tokens", 0) or 0),
        output_tokens=int(payload.get("completion_tokens", 0) or 0),
        cached_input_tokens=int(details.get("cached_tokens", 0) or 0),
    )


class OpenAICompatProvider:
    supports_chat = True
    supports_embeddings = True
    supports_temperature = True

    def __init__(
        self,
        name: str,
        *,
        base_url: str,
        locality: Locality,
        api_key: str | None = None,
        max_tokens_param: str = "max_tokens",
        stream_include_usage: bool = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.locality = locality
        self._max_tokens_param = max_tokens_param
        self._include_usage = stream_include_usage
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(_CLIENT_TIMEOUT_S, connect=_CONNECT_TIMEOUT_S),
        )

    def _body(self, model: str, request: ChatRequest, *, stream: bool) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages += [{"role": m.role, "content": m.content} for m in request.messages]
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            self._max_tokens_param: request.max_output_tokens,
            "stream": stream,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop:
            body["stop"] = request.stop
        if stream and self._include_usage:
            body["stream_options"] = {"include_usage": True}
        return body

    async def chat(self, model: str, request: ChatRequest) -> ChatResult:
        started = time.perf_counter()
        try:
            response = await self._client.post(
                "/chat/completions", json=self._body(model, request, stream=False)
            )
        except httpx.HTTPError as exc:
            raise _map_transport_error(exc, self.name) from None
        _raise_for_status(response, self.name)
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            finish = _FINISH.get(choice.get("finish_reason") or "", "other")
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderUnavailable("malformed provider response", provider=self.name) from None
        return ChatResult(
            text=text,
            usage=_usage(data.get("usage")),
            provider=self.name,
            model=model,
            finish_reason=finish,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    async def stream(self, model: str, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        started = time.perf_counter()
        parts: list[str] = []
        usage = Usage()
        finish: FinishReason = "other"
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=self._body(model, request, stream=True)
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    _raise_for_status(response, self.name)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except ValueError:
                        raise ProviderUnavailable(
                            "malformed stream chunk", provider=self.name
                        ) from None
                    if chunk.get("usage"):
                        usage = _usage(chunk["usage"])
                    for choice in chunk.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            parts.append(delta)
                            yield TextDelta(text=delta)
                        if choice.get("finish_reason"):
                            finish = _FINISH.get(choice["finish_reason"], "other")
        except httpx.HTTPError as exc:
            raise _map_transport_error(exc, self.name) from None
        yield StreamEnd(
            result=ChatResult(
                text="".join(parts),
                usage=usage,
                provider=self.name,
                model=model,
                finish_reason=finish,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        )

    async def embed(self, model: str, inputs: Sequence[str]) -> tuple[list[list[float]], Usage]:
        try:
            response = await self._client.post(
                "/embeddings", json={"model": model, "input": list(inputs)}
            )
        except httpx.HTTPError as exc:
            raise _map_transport_error(exc, self.name) from None
        _raise_for_status(response, self.name)
        try:
            data = response.json()
            ordered = sorted(data["data"], key=lambda item: item.get("index", 0))
            vectors = [[float(x) for x in item["embedding"]] for item in ordered]
        except (ValueError, KeyError, TypeError):
            raise ProviderUnavailable("malformed provider response", provider=self.name) from None
        if len(vectors) != len(inputs):
            raise ProviderUnavailable("embedding count mismatch", provider=self.name)
        return vectors, _usage(data.get("usage"))

    async def aclose(self) -> None:
        await self._client.aclose()
