"""Chapter 13 exercise: compiling UNTRUSTED metadata filters into parameterised SQL (stdlib only).

Threat model: the filter comes from the user's request or from an LLM that extracted it from the
question ("self-query"). Either way it is untrusted input. The compiler must guarantee:
  1. only allow-listed fields and operators are accepted (unknown -> error, never silently ignored);
  2. values are type-checked and bounded, and are NEVER interpolated into SQL text (parameters only);
  3. the mandatory security predicates (tenant, ACL, not-deleted) are AND-ed OUTSIDE the user filter
     and the user cannot name, override or widen them (no $or can escape the mandatory clause).
Run: python -I docs/exercises/ch13_filter_compiler.py [--mutants]
This is an illustrative compiler for the teaching schema, not a library, and not a substitute for
database-enforced isolation (Chapter 8: row-level security / per-tenant indexes).
"""
from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass

MAX_IN_VALUES = 50
MAX_DEPTH = 3
MAX_CONDITIONS = 20

# field -> (python type, allowed operators, column expression)
USER_FIELDS: dict[str, tuple[type, frozenset[str], str]] = {
    "doc_type":   (str, frozenset({"$eq", "$in"}), "doc_type"),
    "department": (str, frozenset({"$eq", "$in"}), "department"),
    "language":   (str, frozenset({"$eq", "$in"}), "language"),
    "created_at": (dt.date, frozenset({"$gte", "$lte"}), "created_at"),
    "version":    (int, frozenset({"$eq", "$gte", "$lte"}), "version"),
    "tags":       (list, frozenset({"$overlap"}), "tags"),
}
OPS_SQL = {"$eq": "=", "$gte": ">=", "$lte": "<="}
ENUMS = {"doc_type": {"policy", "runbook", "contract", "faq"}, "language": {"en", "de", "fr"}}
MANDATORY = ("tenant_id = %s", "acl_groups && %s", "is_deleted = false")


class FilterError(ValueError):
    pass


@dataclass(frozen=True)
class Compiled:
    sql: str
    params: list


def _typed(field: str, value):
    typ = USER_FIELDS[field][0]
    if typ is list:
        if not isinstance(value, list) or not value or len(value) > MAX_IN_VALUES or not all(isinstance(v, str) for v in value):
            raise FilterError(f"{field}: expected a non-empty list of strings (max {MAX_IN_VALUES})")
        return value
    if typ is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise FilterError(f"{field}: expected int")
        return value
    if typ is dt.date:
        try:
            return dt.date.fromisoformat(value)
        except (TypeError, ValueError) as e:
            raise FilterError(f"{field}: expected ISO date") from e
    if not isinstance(value, str) or not value or len(value) > 100:
        raise FilterError(f"{field}: expected a short non-empty string")
    if field in ENUMS and value not in ENUMS[field]:
        raise FilterError(f"{field}: value not in allowed set")
    return value


def _cond(field: str, spec, params: list, defects: set[str]) -> str:
    if field not in USER_FIELDS and "allow-unknown-field" not in defects:
        raise FilterError(f"unknown or non-filterable field: {field!r}")
    if field not in USER_FIELDS:                                   # mutant path only
        return "TRUE"
    if not isinstance(spec, dict) or not spec:
        raise FilterError(f"{field}: expected an operator object")
    parts = []
    for op, val in spec.items():
        if op not in USER_FIELDS[field][1]:
            raise FilterError(f"{field}: operator {op!r} not allowed")
        col = USER_FIELDS[field][2]
        if op == "$in":
            if not isinstance(val, list) or not val or len(val) > MAX_IN_VALUES:
                raise FilterError(f"{field}: $in needs 1..{MAX_IN_VALUES} values")
            params.append([_typed(field, v) for v in val])
            parts.append(f"{col} = ANY(%s)")
        elif op == "$overlap":
            params.append(_typed(field, val))
            parts.append(f"{col} && %s")
        else:
            v = _typed(field, val)
            if "interpolate-values" in defects:
                parts.append(f"{col} {OPS_SQL[op]} '{v}'")         # mutant: value in SQL text
            else:
                params.append(v)
                parts.append(f"{col} {OPS_SQL[op]} %s")
    return "(" + " AND ".join(parts) + ")"


def _node(node, params: list, defects: set[str], depth: int, counter: list[int]) -> str:
    if depth > MAX_DEPTH and "no-depth-limit" not in defects:
        raise FilterError("filter nested too deeply")
    if not isinstance(node, dict) or not node:
        raise FilterError("filter must be a non-empty object")
    parts = []
    for key, val in node.items():
        counter[0] += 1
        if counter[0] > MAX_CONDITIONS and "no-size-limit" not in defects:
            raise FilterError("too many conditions")
        if key in ("$and", "$or"):
            if not isinstance(val, list) or not val:
                raise FilterError(f"{key} needs a non-empty list")
            joiner = " AND " if key == "$and" else " OR "
            parts.append("(" + joiner.join(_node(v, params, defects, depth + 1, counter) for v in val) + ")")
        else:
            parts.append(_cond(key, val, params, defects))
    return " AND ".join(parts)


def compile_filter(user_filter: dict | None, *, tenant_id: str, groups: list[str], defects: set[str] | None = None) -> Compiled:
    """Return (sql, params). Mandatory predicates come first and are AND-ed outside the user filter."""
    defects = defects or set()
    params: list = []
    clauses: list[str] = []
    if "user-filter-first" in defects and user_filter:             # mutant: user fragment can swallow the rest via OR
        clauses.append(_node(user_filter, params, defects, 1, [0]))
        user_filter = None
    params.extend([tenant_id, groups])
    clauses.extend(MANDATORY if "drop-deleted" not in defects else MANDATORY[:2])
    if "drop-acl" in defects:
        clauses = [c for c in clauses if "acl_groups" not in c]
        params.pop()
    if user_filter:
        clauses.append(_node(user_filter, params, defects, 1, [0]))
    return Compiled(" AND ".join(clauses), params)


def run_checks(defects: set[str] | None = None) -> None:
    d = defects or set()
    T, G = "tenantA", ["g1", "g2"]
    c = lambda f: compile_filter(f, tenant_id=T, groups=G, defects=d)  # noqa: E731

    # 1. mandatory predicates always present, in order, with the caller's identity as parameters
    base = c(None)
    assert base.sql == "tenant_id = %s AND acl_groups && %s AND is_deleted = false", base.sql
    assert base.params == [T, G]

    # 2. a normal filter is AND-ed after the mandatory clause and fully parameterised
    ok = c({"doc_type": {"$in": ["policy", "faq"]}, "created_at": {"$gte": "2025-01-01"}, "tags": {"$overlap": ["hr"]}})
    assert ok.sql.startswith(base.sql + " AND "), ok.sql
    assert "policy" not in ok.sql and "2025" not in ok.sql and "hr" not in ok.sql, "values must never appear in SQL text"
    assert ok.params[:2] == [T, G] and ok.params[2] == ["policy", "faq"] and ok.params[3] == dt.date(2025, 1, 1)

    # 3. unknown / security fields cannot be named by the user
    for evil in ({"tenant_id": {"$eq": "tenantB"}}, {"acl_groups": {"$overlap": ["admin"]}}, {"is_deleted": {"$eq": True}},
                 {"$or": [{"tenant_id": {"$eq": "tenantB"}}, {"doc_type": {"$eq": "faq"}}]}):
        try:
            c(evil)
            raise AssertionError(f"accepted forbidden filter {evil}")
        except FilterError:
            pass

    # 4. an $or in the user filter cannot widen beyond the mandatory clause
    wide = c({"$or": [{"doc_type": {"$eq": "faq"}}, {"department": {"$eq": "legal"}}]})
    assert wide.sql == base.sql + " AND ((doc_type = %s) OR (department = %s))", wide.sql
    assert wide.sql.index("OR") > wide.sql.index("is_deleted"), "OR must live inside its own parentheses, after the mandatory clause"

    # 5. injection-looking values are rejected or end up only as parameters
    inj = c({"department": {"$eq": "x'; DROP TABLE chunks;--"}})
    assert "DROP" not in inj.sql and inj.params[-1] == "x'; DROP TABLE chunks;--"
    for bad in ({"doc_type": {"$eq": "not-a-type"}}, {"version": {"$eq": True}}, {"created_at": {"$gte": "yesterday"}},
                {"department": {"$like": "%"}}, {"doc_type": {"$in": []}}, {"doc_type": {"$in": ["policy"] * 51}}, {"tags": {"$overlap": "hr"}}):
        try:
            c(bad)
            raise AssertionError(f"accepted invalid filter {bad}")
        except FilterError:
            pass

    # 6. resource limits
    deep = {"$and": [{"$and": [{"$and": [{"$and": [{"version": {"$eq": 1}}]}]}]}]}
    try:
        c(deep)
        raise AssertionError("accepted over-deep filter")
    except FilterError:
        pass
    many = {"$and": [{"version": {"$gte": i}} for i in range(MAX_CONDITIONS + 5)]}
    try:
        c(many)
        raise AssertionError("accepted over-large filter")
    except FilterError:
        pass


def main() -> None:
    T, G = "tenantA", ["g1"]
    r = compile_filter({"doc_type": {"$eq": "policy"}, "created_at": {"$gte": "2025-01-01"}}, tenant_id=T, groups=G)
    print("SQL   :", r.sql)
    print("params:", r.params)
    run_checks()
    print("OK: all assertions hold (illustrative compiler, constructed inputs).")


def mutants() -> None:
    names = ["allow-unknown-field", "interpolate-values", "drop-deleted", "drop-acl", "user-filter-first", "no-depth-limit", "no-size-limit"]
    survived = []
    for m in names:
        try:
            run_checks({m})
            survived.append(m)
        except (AssertionError, FilterError, KeyError, IndexError):
            print(f"  mutant killed: {m}")
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(names)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
