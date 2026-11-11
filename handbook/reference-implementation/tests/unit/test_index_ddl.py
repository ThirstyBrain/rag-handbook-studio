"""Per-space vector index DDL and query expressions (ADR-019). Pure functions; no database needed."""

from __future__ import annotations

import pytest

from rag_service.features.indexing.ddl import IndexSpecError, VectorIndexSpec


def test_small_dimensions_use_a_vector_expression_index_partial_on_the_space() -> None:
    spec = VectorIndexSpec(space="openai:te3-small", dimensions=1536)
    sql = spec.create_index_sql()
    assert "USING hnsw ((embedding::vector(1536)) vector_cosine_ops)" in sql
    assert "WITH (m = 16, ef_construction = 64)" in sql
    assert sql.endswith("WHERE embedding_space = 'openai:te3-small' AND dimensions = 1536")
    assert sql.startswith("CREATE INDEX CONCURRENTLY IF NOT EXISTS ce_")


def test_dimensions_above_the_vector_limit_use_halfvec() -> None:
    spec = VectorIndexSpec(space="big", dimensions=3072)
    assert spec.column_type == "halfvec"
    assert "(embedding::halfvec(3072)) halfvec_cosine_ops" in spec.create_index_sql()


def test_the_boundary_is_2000_for_vector() -> None:
    assert VectorIndexSpec(space="s", dimensions=2000).column_type == "vector"
    assert VectorIndexSpec(space="s", dimensions=2001).column_type == "halfvec"


def test_query_expression_repeats_the_index_cast_so_the_planner_can_use_it() -> None:
    spec = VectorIndexSpec(space="s", dimensions=768)
    assert spec.distance_expression() == "(embedding::vector(768)) <=> %s::vector(768)"
    assert spec.query_predicate() == "embedding_space = %s AND dimensions = 768"
    # the index expression and the query expression share the same cast text
    assert spec.cast in spec.create_index_sql() and spec.cast in spec.distance_expression()


@pytest.mark.parametrize(
    ("metric", "ops", "operator"),
    [
        ("cosine", "vector_cosine_ops", "<=>"),
        ("inner_product", "vector_ip_ops", "<#>"),
        ("l2", "vector_l2_ops", "<->"),
    ],
)
def test_each_metric_maps_to_its_operator_class_and_operator(
    metric: str, ops: str, operator: str
) -> None:
    spec = VectorIndexSpec(space="s", dimensions=8, metric=metric)  # type: ignore[arg-type]
    assert ops in spec.create_index_sql()
    assert f") {operator} " in spec.distance_expression()


def test_index_names_are_deterministic_unique_per_space_and_within_the_identifier_limit() -> None:
    a = VectorIndexSpec(space="a", dimensions=8)
    assert a.index_name == VectorIndexSpec(space="a", dimensions=8).index_name
    assert a.index_name != VectorIndexSpec(space="b", dimensions=8).index_name
    assert a.index_name != VectorIndexSpec(space="a", dimensions=9).index_name
    assert (
        len(VectorIndexSpec(space="x" * 64, dimensions=4000, metric="inner_product").index_name)
        <= 63
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"space": "bad space", "dimensions": 8},
        {"space": "x'; DROP TABLE rag.chunks; --", "dimensions": 8},
        {"space": "", "dimensions": 8},
        {"space": "s" * 65, "dimensions": 8},
        {"space": "s", "dimensions": 0},
        {"space": "s", "dimensions": 4001},
        {"space": "s", "dimensions": 8, "m": 1},
        {"space": "s", "dimensions": 8, "m": 16, "ef_construction": 31},
        {"space": "s", "dimensions": 8, "ef_construction": 1001},
    ],
)
def test_unsafe_or_unsupported_specs_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(IndexSpecError):
        VectorIndexSpec(**kwargs)  # type: ignore[arg-type]
