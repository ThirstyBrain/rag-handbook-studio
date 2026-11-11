"""Turn chunks into vectors through the gateway's embed route (ADR-017).

The embedder sees chunk text in memory only; it never reads the database. Its output is validated as
untrusted provider data: count, dimension, finiteness, non-zero norm and a stable embedding space.
"""

from __future__ import annotations

import math
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from rag_service.features.chunking.chunker import Chunk
from rag_service.features.extraction.model import Rejected
from rag_service.features.llm.errors import ContentRefused, InvalidRequest
from rag_service.features.llm.types import EmbedRequest, EmbedResult, Sensitivity

T = TypeVar("T")

# What text is embedded for a chunk. Changing this changes every vector, so it is part of the stored
# identity of an embedding and a change means re-embedding (ADR-017).
RECIPE = "section-path-prefix-v1"


class EmbedPort(Protocol):
    async def embed(self, request: EmbedRequest) -> EmbedResult: ...


class Runner(Protocol):
    def run(self, coro: Coroutine[Any, Any, T], timeout_s: float) -> T: ...


class EmbeddingError(Exception):
    """The provider answered, but not with something that can be stored. Retried like an outage."""


@dataclass(frozen=True)
class EmbeddingConfig:
    route: str = "embed"
    batch_size: int = 32
    max_dimensions: int = 4000
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    call_timeout_s: float = 120.0

    def __post_init__(self) -> None:
        if self.batch_size < 1 or not 1 <= self.max_dimensions <= 4000 or self.call_timeout_s <= 0:
            raise ValueError("invalid embedding configuration")


@dataclass(frozen=True)
class EmbeddedChunks:
    vectors: list[list[float]]
    models: list[str]  # per chunk: a fallback may change the model inside one embedding space
    space: str
    dimensions: int
    recipe: str
    input_tokens: int
    calls: int
    attempts: int
    fallback_used: bool


def embedding_input(chunk: Chunk) -> str:
    """The text that represents a chunk: its section path (context the chunk text lacks) then its content."""
    return f"{chunk.section_path}\n\n{chunk.content}" if chunk.section_path else chunk.content


class ChunkEmbedder:
    def __init__(self, gateway: EmbedPort, config: EmbeddingConfig, runner: Runner) -> None:
        self._gateway = gateway
        self._config = config
        self._runner = runner

    def embed(self, chunks: Sequence[Chunk]) -> EmbeddedChunks:
        """Embed all chunks or raise. ``Rejected`` means retrying cannot help; anything else is retried."""
        if not chunks:
            raise ValueError("nothing to embed")
        texts = [embedding_input(c) for c in chunks]
        size = self._config.batch_size
        vectors: list[list[float]] = []
        models: list[str] = []
        space = ""
        dims = 0
        tokens = attempts = calls = 0
        fallback = False
        for start in range(0, len(texts), size):
            batch = texts[start : start + size]
            result = self._call(batch)
            self._validate(result, len(batch))
            if calls == 0:
                space, dims = result.embedding_space, result.dimensions
            elif result.embedding_space != space or result.dimensions != dims:
                raise EmbeddingError("embedding space changed during one version")
            vectors.extend(result.vectors)
            models.extend([result.model] * len(batch))
            tokens += result.usage.input_tokens
            attempts += result.attempts
            fallback = fallback or result.fallback_used
            calls += 1
        return EmbeddedChunks(
            vectors=vectors,
            models=models,
            space=space,
            dimensions=dims,
            recipe=RECIPE,
            input_tokens=tokens,
            calls=calls,
            attempts=attempts,
            fallback_used=fallback,
        )

    def _call(self, batch: list[str]) -> EmbedResult:
        request = EmbedRequest(
            route=self._config.route, inputs=batch, sensitivity=self._config.sensitivity
        )
        try:
            return self._runner.run(self._gateway.embed(request), self._config.call_timeout_s)
        except (InvalidRequest, ContentRefused):
            # the same input will be refused again: end the job and mark the version failed
            raise Rejected("embedding_rejected") from None

    def _validate(self, result: EmbedResult, expected: int) -> None:
        if not result.embedding_space:
            raise EmbeddingError("embedding route has no embedding_space")
        if len(result.vectors) != expected:
            raise EmbeddingError("provider returned the wrong number of vectors")
        if not 1 <= result.dimensions <= self._config.max_dimensions:
            raise EmbeddingError("embedding dimension outside the supported range")
        for vector in result.vectors:
            if len(vector) != result.dimensions:
                raise EmbeddingError("embedding dimension mismatch")
            if not all(math.isfinite(x) for x in vector):
                raise EmbeddingError("embedding contains a non-finite value")
            if not any(vector):
                raise EmbeddingError("embedding is the zero vector")
