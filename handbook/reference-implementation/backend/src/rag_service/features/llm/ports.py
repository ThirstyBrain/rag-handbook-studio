"""The port every provider adapter implements. The gateway depends only on this."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Literal, Protocol

from rag_service.features.llm.types import ChatRequest, ChatResult, StreamEvent, Usage

Locality = Literal["local", "external"]


class LlmProvider(Protocol):
    name: str
    locality: Locality
    supports_chat: bool
    supports_embeddings: bool
    # False for providers whose API rejects a temperature parameter (current Claude models).
    supports_temperature: bool

    async def chat(self, model: str, request: ChatRequest) -> ChatResult: ...

    def stream(self, model: str, request: ChatRequest) -> AsyncIterator[StreamEvent]: ...

    async def embed(self, model: str, inputs: Sequence[str]) -> tuple[list[list[float]], Usage]: ...

    async def aclose(self) -> None: ...
