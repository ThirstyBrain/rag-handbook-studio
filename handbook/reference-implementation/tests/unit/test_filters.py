"""The metadata filter compiler (ADR-009): allow-list, typed values, bind parameters only, size limits."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rag_service.features.retrieval.filters import (
    MAX_CONDITIONS,
    MAX_IN_VALUES,
    MAX_TEXT_CHARS,
    NO_FILTER,
    Condition,
    FilterError,
    compile_filters,
)
from rag_service.features.retrieval.query import QueryError


def c(field: str, op: str, value: str | list[str]) -> Condition:
    return Condition(field=field, op=op, value=value)  # type: ignore[arg-type]


def test_no_conditions_means_no_filter() -> None:
    assert compile_filters([]) is NO_FILTER or compile_filters([]) == NO_FILTER
    assert NO_FILTER.sql == "" and NO_FILTER.params == ()


def test_each_operator_compiles_to_a_placeholder_clause() -> None:
    doc = uuid4()
    compiled = compile_filters(
        [
            c("source_id", "prefix", "hr/"),
            c("classification", "in", ["public", "internal"]),
            c("document_id", "eq", str(doc)),
            c("updated_at", "gte", "2026-01-01T00:00:00+00:00"),
            c("updated_at", "lte", "2026-12-31T00:00:00+00:00"),
            c("extractor", "eq", "markdown-1"),
            c("section_path", "prefix", "Handbook > Leave"),
        ]
    )
    assert compiled.sql == (
        " AND (starts_with(d.source_id, %s))"
        " AND (d.classification = ANY(%s))"
        " AND (d.document_id = %s)"
        " AND (d.updated_at >= %s)"
        " AND (d.updated_at <= %s)"
        " AND (v.extractor = %s)"
        " AND (starts_with(c.section_path, %s))"
    )
    assert compiled.params[0] == "hr/"
    assert compiled.params[1] == ["public", "internal"]
    assert compiled.params[2] == doc
    assert compiled.params[3] == datetime(2026, 1, 1, tzinfo=UTC)
    assert len(compiled.params) == compiled.sql.count("%s")


def test_values_never_appear_in_the_sql_text() -> None:
    hostile = "x'); DROP TABLE rag.chunks; --"
    compiled = compile_filters([c("source_id", "eq", hostile)])
    assert hostile not in compiled.sql and compiled.params == (hostile,)


@pytest.mark.parametrize(
    "field", ["tenant_id", "acl_groups", "status", "state", "content", "d.status", "version"]
)
def test_mandatory_and_unlisted_columns_cannot_be_named(field: str) -> None:
    with pytest.raises(ValidationError):  # the field names are a closed Literal
        Condition(field=field, op="eq", value="x")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "cond",
    [
        ("classification", "prefix", "pub"),
        ("document_id", "gte", "x"),
        ("updated_at", "eq", "2026-01-01T00:00:00+00:00"),
        ("section_path", "in", ["a"]),
    ],
)
def test_an_operator_not_allowed_for_the_field_is_rejected(cond: tuple[str, str, object]) -> None:
    with pytest.raises(FilterError):
        compile_filters([c(*cond)])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "cond",
    [
        ("document_id", "eq", "not-a-uuid"),
        ("document_id", "in", ["not-a-uuid"]),
        ("updated_at", "gte", "yesterday"),
        ("updated_at", "gte", "2026-01-01T00:00:00"),  # naive timestamp: ambiguous, refused
        ("classification", "eq", "secret"),
        ("source_id", "eq", "a\x00b"),
        ("source_id", "eq", "x" * (MAX_TEXT_CHARS + 1)),
    ],
)
def test_invalid_values_are_rejected(cond: tuple[str, str, object]) -> None:
    with pytest.raises(FilterError):
        compile_filters([c(*cond)])  # type: ignore[arg-type]


def test_shape_errors_between_scalar_and_list() -> None:
    with pytest.raises(FilterError):
        compile_filters([c("source_id", "eq", ["a"])])
    with pytest.raises(FilterError):
        compile_filters([c("source_id", "in", "a")])
    with pytest.raises(FilterError):
        compile_filters([c("source_id", "in", [])])


def test_size_limits() -> None:
    with pytest.raises(FilterError):
        compile_filters([c("source_id", "in", [str(i) for i in range(MAX_IN_VALUES + 1)])])
    ok = compile_filters([c("source_id", "in", [str(i) for i in range(MAX_IN_VALUES)])])
    assert len(ok.params[0]) == MAX_IN_VALUES  # type: ignore[arg-type]
    # distinct (field, op) pairs, so only the count limit can reject them (not the duplicate rule)
    distinct = [
        c("source_id", "eq", "a"),
        c("source_id", "in", ["a"]),
        c("source_id", "prefix", "a"),
        c("classification", "eq", "public"),
        c("classification", "in", ["public"]),
        c("section_path", "eq", "a"),
        c("section_path", "prefix", "a"),
        c("extractor", "eq", "a"),
        c("extractor", "in", ["a"]),
    ]
    assert len(distinct) == MAX_CONDITIONS + 1
    compile_filters(distinct[:MAX_CONDITIONS])  # at the limit: accepted
    with pytest.raises(FilterError, match="at most"):
        compile_filters(distinct)


def test_a_repeated_field_and_operator_pair_is_rejected_but_a_range_is_allowed() -> None:
    with pytest.raises(FilterError):
        compile_filters([c("source_id", "eq", "a"), c("source_id", "eq", "b")])
    compile_filters(
        [
            c("updated_at", "gte", "2026-01-01T00:00:00Z"),
            c("updated_at", "lte", "2026-02-01T00:00:00Z"),
        ]
    )


def test_filter_errors_are_query_errors_so_the_api_maps_them_to_422() -> None:
    assert issubclass(FilterError, QueryError)


def test_unknown_keys_on_a_condition_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        Condition.model_validate({"field": "source_id", "op": "eq", "value": "a", "raw_sql": "1=1"})
