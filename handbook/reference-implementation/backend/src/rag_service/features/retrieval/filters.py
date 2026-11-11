"""The metadata filter compiler (ADR-009): caller-supplied conditions become a parameterised SQL fragment.

Rules, all enforced here and tested without a database:
  * only allow-listed fields and per-field operators exist; anything else is rejected, so a user or an
    LLM-produced filter cannot name tenant, ACL, status or lifecycle columns;
  * values are typed (uuid, timestamp, enum, bounded text) and always travel as bind parameters; the only
    text interpolated into SQL is a column expression taken from the allow-list below;
  * size limits bound the work a caller can request;
  * the fragment is AND-ed AFTER the platform's mandatory predicates (tenant, ACL, active version), which
    this module never builds and a filter can never relax.
Missing values: every filterable column is NOT NULL in the schema, so no condition needs a NULL policy;
add one per attribute before filtering on a nullable column (ADR-009 decision 7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rag_service.features.retrieval.query import QueryError

Operator = Literal["eq", "in", "gte", "lte", "prefix"]
FieldName = Literal[
    "source_id", "classification", "document_id", "section_path", "updated_at", "extractor"
]

MAX_CONDITIONS = 8
MAX_IN_VALUES = 50
MAX_TEXT_CHARS = 1000
CLASSIFICATIONS = frozenset({"public", "internal", "restricted"})


class FilterError(QueryError):
    """The filter is not allowed or not valid; the message is safe to return to the caller."""


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: FieldName
    op: Operator
    value: str | list[str] = Field(...)


@dataclass(frozen=True)
class _Field:
    column: str  # an identifier from this table only, never from input
    kind: Literal["text", "uuid", "timestamp", "enum"]
    ops: frozenset[Operator]


_FIELDS: dict[str, _Field] = {
    "source_id": _Field("d.source_id", "text", frozenset({"eq", "in", "prefix"})),
    "classification": _Field("d.classification", "enum", frozenset({"eq", "in"})),
    "document_id": _Field("d.document_id", "uuid", frozenset({"eq", "in"})),
    "section_path": _Field("c.section_path", "text", frozenset({"eq", "prefix"})),
    "updated_at": _Field("d.updated_at", "timestamp", frozenset({"gte", "lte"})),
    "extractor": _Field("v.extractor", "text", frozenset({"eq", "in"})),
}


@dataclass(frozen=True)
class CompiledFilter:
    sql: str  # "" or " AND (...) AND (...)" with %s placeholders
    params: tuple[object, ...]


NO_FILTER = CompiledFilter("", ())


def _scalar(spec: _Field, field: str, raw: str) -> object:
    if len(raw) > MAX_TEXT_CHARS:
        raise FilterError(f"value for {field} is longer than {MAX_TEXT_CHARS} characters")
    if spec.kind == "uuid":
        try:
            return UUID(raw)
        except ValueError:
            raise FilterError(f"value for {field} is not a UUID") from None
    if spec.kind == "timestamp":
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            raise FilterError(f"value for {field} is not an ISO 8601 timestamp") from None
        if parsed.tzinfo is None:
            raise FilterError(f"timestamp for {field} must include a UTC offset")
        return parsed
    if spec.kind == "enum":
        if raw not in CLASSIFICATIONS:
            raise FilterError(f"{field} must be one of {sorted(CLASSIFICATIONS)}")
        return raw
    if "\x00" in raw:
        raise FilterError(f"value for {field} contains a NUL character")
    return raw


def compile_filters(conditions: Sequence[Condition]) -> CompiledFilter:
    if not conditions:
        return NO_FILTER
    if len(conditions) > MAX_CONDITIONS:
        raise FilterError(f"at most {MAX_CONDITIONS} filter conditions are allowed")
    seen: set[tuple[str, str]] = set()
    clauses: list[str] = []
    params: list[object] = []
    for cond in conditions:
        spec = _FIELDS.get(cond.field)
        if spec is None or cond.op not in spec.ops:
            raise FilterError(f"operator {cond.op!r} is not allowed on field {cond.field!r}")
        if (cond.field, cond.op) in seen:
            raise FilterError(f"duplicate condition on {cond.field} {cond.op}")
        seen.add((cond.field, cond.op))
        if cond.op == "in":
            if not isinstance(cond.value, list) or not 1 <= len(cond.value) <= MAX_IN_VALUES:
                raise FilterError(f"'in' on {cond.field} needs 1 to {MAX_IN_VALUES} values")
            clauses.append(f"{spec.column} = ANY(%s)")
            params.append([_scalar(spec, cond.field, v) for v in cond.value])
            continue
        if not isinstance(cond.value, str):
            raise FilterError(f"'{cond.op}' on {cond.field} needs a single value")
        value = _scalar(spec, cond.field, cond.value)
        if cond.op == "eq":
            clauses.append(f"{spec.column} = %s")
        elif cond.op == "gte":
            clauses.append(f"{spec.column} >= %s")
        elif cond.op == "lte":
            clauses.append(f"{spec.column} <= %s")
        else:  # prefix: starts_with avoids LIKE wildcard escaping
            clauses.append(f"starts_with({spec.column}, %s)")
        params.append(value)
    return CompiledFilter("".join(f" AND ({c})" for c in clauses), tuple(params))
