"""Adapter for Claude through the official ``anthropic`` SDK (imported lazily).

Design points verified against the SDK documentation and the installed SDK (anthropic 2.6.0):
- SDK retries are disabled (``max_retries=0``): the gateway owns retry, backoff and fallback.
- ``temperature`` is never sent: current Claude models reject it, so ``supports_temperature`` is False.
- Thinking is not configured here; the model's default applies. Thinking tokens count toward
  ``max_tokens``, so give Claude routes a generous ``max_output_tokens``.
- Embeddings are not offered by this API; use another provider for embedding routes.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any

from rag_service.features.llm.errors import (
    ContentRefused,
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

if TYPE_CHECKING:
    import anthropic

_STOP: dict[str, FinishReason] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "refusal": "refusal",
}


def _import_anthropic() -> Any:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - exercised only without the optional dependency
        raise RuntimeError(
            "provider kind 'anthropic' needs the 'anthropic' package (requirements.txt)"
        ) from exc
    return anthropic


def _usage(raw: Any) -> Usage:
    if raw is None:
        return Usage()
    return Usage(
        input_tokens=int(getattr(raw, "input_tokens", 0) or 0),
        output_tokens=int(getattr(raw, "output_tokens", 0) or 0),
        cached_input_tokens=int(getattr(raw, "cache_read_input_tokens", 0) or 0),
    )


def map_anthropic_error(exc: Exception, provider: str) -> LlmError:
    """Classify SDK exceptions by type and status code; never copy the SDK message (it can echo input)."""
    sdk = _import_anthropic()
    if isinstance(exc, sdk.APITimeoutError):  # subclass of APIConnectionError: check first
        return ProviderTimeout("provider timed out", provider=provider)
    if isinstance(exc, sdk.APIConnectionError):
        return ProviderUnavailable("provider unreachable", provider=provider)
    if isinstance(exc, sdk.APIStatusError):
        status = int(exc.status_code)
        if status == 429:
            retry_after: float | None = None
            raw = exc.response.headers.get("retry-after")
            try:
                retry_after = float(raw) if raw is not None else None
            except ValueError:
                retry_after = None
            return RateLimited("rate limited", provider=provider, retry_after_s=retry_after)
        if status in (401, 403):
            return ProviderAuthError("credentials rejected", provider=provider)
        if status == 408:
            return ProviderTimeout("provider timed out", provider=provider)
        if status == 404:  # unknown model
            return TargetUnsupported(
                "target does not support this request (404)", provider=provider
            )
        if status >= 500:  # includes 529 overloaded
            return ProviderUnavailable("provider error", provider=provider)
        return InvalidRequest(f"request rejected with status {status}", provider=provider)
    return ProviderUnavailable("unexpected provider failure", provider=provider)


class AnthropicProvider:
    supports_chat = True
    supports_embeddings = False
    supports_temperature = False

    def __init__(
        self,
        name: str,
        *,
        api_key: str | None,
        locality: Locality = "external",
        base_url: str | None = None,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        sdk = _import_anthropic()
        self.name = name
        self.locality = locality
        kwargs: dict[str, Any] = {"max_retries": 0}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = client or sdk.AsyncAnthropic(**kwargs)

    @staticmethod
    def _params(model: str, request: ChatRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.system:
            params["system"] = request.system
        if request.stop:
            params["stop_sequences"] = request.stop
        return params

    def _result(self, message: Any, model: str, started: float) -> ChatResult:
        text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
        return ChatResult(
            text=text,
            usage=_usage(message.usage),
            provider=self.name,
            model=model,
            finish_reason=_STOP.get(message.stop_reason or "", "other"),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    async def chat(self, model: str, request: ChatRequest) -> ChatResult:
        started = time.perf_counter()
        try:
            message = await self._client.messages.create(**self._params(model, request))
        except Exception as exc:
            raise map_anthropic_error(exc, self.name) from None
        result = self._result(message, model, started)
        if result.finish_reason == "refusal":
            raise ContentRefused("provider declined the request", provider=self.name)
        return result

    async def stream(self, model: str, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        started = time.perf_counter()
        try:
            async with self._client.messages.stream(**self._params(model, request)) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text=text)
                message = await stream.get_final_message()
        except Exception as exc:
            raise map_anthropic_error(exc, self.name) from None
        result = self._result(message, model, started)
        if result.finish_reason == "refusal":
            raise ContentRefused("provider declined the request", provider=self.name)
        yield StreamEnd(result=result)

    async def embed(self, model: str, inputs: Sequence[str]) -> tuple[list[list[float]], Usage]:
        raise InvalidRequest("this provider does not offer embeddings", provider=self.name)

    async def aclose(self) -> None:
        await self._client.close()
