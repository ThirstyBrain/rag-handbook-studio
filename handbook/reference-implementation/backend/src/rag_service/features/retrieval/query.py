"""Validation of the user's query and of the query embedding (both are untrusted input)."""

from __future__ import annotations

import math
from collections.abc import Sequence

MAX_QUERY_CHARS = 2000


class QueryError(ValueError):
    """The query cannot be searched; the message is safe to return to the caller."""


def normalise_query(text: str) -> str:
    """Trim and collapse whitespace; reject empty, oversize and control-character input."""
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text):
        raise QueryError("query contains control characters")
    cleaned = " ".join(text.split())
    if not cleaned:
        raise QueryError("query is empty")
    if len(cleaned) > MAX_QUERY_CHARS:
        raise QueryError(f"query is longer than {MAX_QUERY_CHARS} characters")
    return cleaned


def validate_query_vector(vector: Sequence[float], dimensions: int, max_dimensions: int) -> None:
    """The provider's vector is untrusted: right size, finite, not all zeros (cosine is undefined there)."""
    if not 1 <= dimensions <= max_dimensions or len(vector) != dimensions:
        raise QueryError("query embedding has an unexpected dimension")
    if not all(math.isfinite(x) for x in vector):
        raise QueryError("query embedding contains non-finite values")
    if not any(vector):
        raise QueryError("query embedding is a zero vector")


def vector_literal(vector: Sequence[float]) -> str:
    """pgvector text input format; values were validated finite, so no escaping is needed."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
