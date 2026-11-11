"""Provider-neutral request/response types for the LLM gateway.

Nothing here knows about any vendor. Application code builds a ``ChatRequest`` or ``EmbedRequest``
naming a *route* (a purpose such as "answer" or "embed"), never a vendor or a model.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Sensitivity(StrEnum):
    """How sensitive the prompt content is. ``RESTRICTED`` may only be sent to local providers."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Message(_Frozen):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(_Frozen):
    route: str = Field(min_length=1, max_length=64)
    messages: list[Message] = Field(min_length=1)
    system: str | None = None
    max_output_tokens: int = Field(default=1024, gt=0)
    # Ignored by providers that do not accept it (for example Claude models, which reject it).
    temperature: float | None = Field(default=None, ge=0, le=2)
    stop: list[str] | None = None
    sensitivity: Sensitivity = Sensitivity.INTERNAL


class Usage(_Frozen):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


FinishReason = Literal["stop", "length", "refusal", "other"]


class ChatResult(_Frozen):
    text: str
    usage: Usage
    provider: str
    model: str
    finish_reason: FinishReason
    latency_ms: float
    attempts: int = 1
    fallback_used: bool = False
    estimated_cost_usd: float | None = None


class TextDelta(_Frozen):
    text: str


class StreamEnd(_Frozen):
    result: ChatResult


StreamEvent = TextDelta | StreamEnd


class EmbedRequest(_Frozen):
    route: str = Field(min_length=1, max_length=64)
    inputs: list[str] = Field(min_length=1)
    sensitivity: Sensitivity = Sensitivity.INTERNAL


class EmbedResult(_Frozen):
    vectors: list[list[float]]
    usage: Usage
    provider: str
    model: str
    embedding_space: str
    dimensions: int
    latency_ms: float
    attempts: int = 1
    fallback_used: bool = False
    estimated_cost_usd: float | None = None
