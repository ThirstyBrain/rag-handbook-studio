"""DDL and query expressions for per-embedding-space vector indexes (ADR-019).

pgvector indexes need a fixed dimension, but ``rag.chunk_embeddings.embedding`` is an unconstrained
``vector`` because dimension depends on the model (ADR-017). The documented workaround is an expression
index that casts to the space's dimension, made partial on ``embedding_space`` so each space has its own
index. A query only uses such an index if it repeats the same cast expression, so the DDL and the query
expression are generated from one spec here and cannot drift.

Limits taken from the pgvector README (SRC-131, read at README level): HNSW indexes ``vector`` up to 2000
dimensions and ``halfvec`` up to 4000, so spaces above 2000 dimensions are indexed as ``halfvec``
(16-bit precision: a recall/size trade that must be measured, not assumed). Pure functions, no database.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

Metric = Literal["cosine", "inner_product", "l2"]

SPACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")  # identical to the CHECK in migration 0004
MAX_VECTOR_DIMENSIONS = 2000
MAX_HALFVEC_DIMENSIONS = 4000

# metric -> (operator class suffix, query operator)
_METRICS: dict[Metric, tuple[str, str]] = {
    "cosine": ("cosine_ops", "<=>"),
    "inner_product": ("ip_ops", "<#>"),
    "l2": ("l2_ops", "<->"),
}


class IndexSpecError(ValueError):
    """The requested index cannot be created safely."""


@dataclass(frozen=True)
class VectorIndexSpec:
    space: str
    dimensions: int
    metric: Metric = "cosine"
    m: int = 16
    ef_construction: int = 64

    def __post_init__(self) -> None:
        if not SPACE_PATTERN.fullmatch(self.space):
            raise IndexSpecError("embedding space must match [A-Za-z0-9._:-]{1,64}")
        if not 1 <= self.dimensions <= MAX_HALFVEC_DIMENSIONS:
            raise IndexSpecError(f"dimensions must be between 1 and {MAX_HALFVEC_DIMENSIONS}")
        if self.metric not in _METRICS:
            raise IndexSpecError(f"unknown metric {self.metric!r}")
        if not 2 <= self.m <= 100:
            raise IndexSpecError("m must be between 2 and 100")
        if not (self.m * 2 <= self.ef_construction <= 1000):
            raise IndexSpecError("ef_construction must be at least 2*m and at most 1000")

    @property
    def column_type(self) -> Literal["vector", "halfvec"]:
        return "vector" if self.dimensions <= MAX_VECTOR_DIMENSIONS else "halfvec"

    @property
    def index_name(self) -> str:
        """Deterministic, collision-resistant and always within PostgreSQL's 63-byte identifier limit."""
        digest = hashlib.sha256(self.space.encode()).hexdigest()[:12]
        return f"ce_{digest}_{self.dimensions}_{self.metric}_hnsw"

    @property
    def cast(self) -> str:
        """The expression the index is built on, e.g. ``embedding::vector(1536)``."""
        return f"embedding::{self.column_type}({self.dimensions})"

    def create_index_sql(self) -> str:
        """``CREATE INDEX CONCURRENTLY`` must run outside a transaction (autocommit)."""
        ops = f"{self.column_type}_{_METRICS[self.metric][0]}"
        return (
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {self.index_name} "
            f"ON rag.chunk_embeddings USING hnsw (({self.cast}) {ops}) "
            f"WITH (m = {self.m}, ef_construction = {self.ef_construction}) "
            f"WHERE embedding_space = '{self.space}' AND dimensions = {self.dimensions}"
        )

    def distance_expression(self, param: str = "%s", alias: str = "") -> str:
        """The ordering expression a query must use for the planner to consider this index.

        ``param`` is a driver placeholder (never a value); ``alias`` qualifies the columns when the query
        joins (a fixed identifier from code, e.g. ``e``). The query must also repeat the partial-index
        predicate (``query_predicate``) so the planner can prove the index applies."""
        operator = _METRICS[self.metric][1]
        prefix = f"{alias}." if alias else ""
        return f"({prefix}{self.cast}) {operator} {param}::{self.column_type}({self.dimensions})"

    def query_predicate(self, alias: str = "") -> str:
        """The partial-index predicate, with the space as a placeholder and the dimension as a literal."""
        prefix = f"{alias}." if alias else ""
        return f"{prefix}embedding_space = %s AND {prefix}dimensions = {self.dimensions}"
