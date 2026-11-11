"""Deterministic offline provider for tests and for running the whole application with no model.

Never allowed in production (the builder refuses ``kind = "fake"`` when ``allow_fake`` is False).
It can be scripted to fail so gateway behaviour (retry, fallback, breaker) is testable without a network.
"""

from __future__ import annotations

import hashlib
import math
from collections import deque
from collections.abc import AsyncIterator, Sequence

from rag_service.features.llm.errors import LlmError
from rag_service.features.llm.ports import Locality
from rag_service.features.llm.types import (
    ChatRequest,
    ChatResult,
    StreamEnd,
    StreamEvent,
    TextDelta,
    Usage,
)

FAKE_DIMENSIONS = 16


class FakeProvider:
    supports_chat = True
    supports_embeddings = True
    supports_temperature = True

    def __init__(
        self,
        name: str,
        *,
        locality: Locality = "local",
        outcomes: Sequence[LlmError | str] | None = None,
    ) -> None:
        self.name = name
        self.locality = locality
        # Each call consumes one outcome: an exception is raised, a string becomes the reply text.
        self._outcomes: deque[LlmError | str] = deque(outcomes or [])
        self.calls: list[tuple[str, str]] = []  # (operation, model)
        self.seen_temperatures: list[float | None] = []
        self.seen_max_tokens: list[int] = []

    def _next(self, request_text: str) -> str:
        if self._outcomes:
            outcome = self._outcomes.popleft()
            if isinstance(outcome, LlmError):
                raise outcome
            return outcome
        return f"[{self.name}] reply to {len(request_text)} chars"

    async def chat(self, model: str, request: ChatRequest) -> ChatResult:
        self.calls.append(("chat", model))
        self.seen_temperatures.append(request.temperature)
        self.seen_max_tokens.append(request.max_output_tokens)
        text = self._next("".join(m.content for m in request.messages))
        return ChatResult(
            text=text,
            usage=Usage(
                input_tokens=max(1, sum(len(m.content) for m in request.messages) // 4),
                output_tokens=max(1, len(text) // 4),
            ),
            provider=self.name,
            model=model,
            finish_reason="stop",
            latency_ms=1.0,
        )

    async def stream(self, model: str, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.calls.append(("stream", model))
        text = self._next("".join(m.content for m in request.messages))
        for word in text.split(" "):
            yield TextDelta(text=word + " ")
        yield StreamEnd(
            result=ChatResult(
                text=text + " ",
                usage=Usage(input_tokens=1, output_tokens=max(1, len(text) // 4)),
                provider=self.name,
                model=model,
                finish_reason="stop",
                latency_ms=1.0,
            )
        )

    async def embed(self, model: str, inputs: Sequence[str]) -> tuple[list[list[float]], Usage]:
        self.calls.append(("embed", model))
        if self._outcomes:
            outcome = self._outcomes.popleft()
            if isinstance(outcome, LlmError):
                raise outcome
        vectors = []
        for text in inputs:
            digest = hashlib.sha256(text.encode()).digest()
            raw = [(digest[i] - 127.5) for i in range(FAKE_DIMENSIONS)]
            norm = math.sqrt(sum(x * x for x in raw)) or 1.0
            vectors.append([x / norm for x in raw])
        return vectors, Usage(input_tokens=sum(max(1, len(t) // 4) for t in inputs))

    async def aclose(self) -> None:
        return None
