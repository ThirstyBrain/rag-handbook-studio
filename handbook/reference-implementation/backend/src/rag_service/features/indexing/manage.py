"""Create the vector index for one embedding space (ADR-019). Run by an operator as the owner role.

    python -m rag_service.features.indexing.manage --space fake-v1 --dimensions 64 [--metric cosine]

Uses RAG_MIGRATION_DATABASE_URL. ``CREATE INDEX CONCURRENTLY`` cannot run inside a transaction, so the
connection is autocommit. If the build is interrupted PostgreSQL leaves an INVALID index; this command
detects that, drops it and rebuilds, so re-running is always safe.
"""

from __future__ import annotations

import argparse
import logging
import sys

import psycopg

from rag_service.core.config import Settings
from rag_service.features.indexing.ddl import IndexSpecError, VectorIndexSpec

_log = logging.getLogger(__name__)

_INVALID = (
    "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'rag' AND c.relname = %s AND NOT i.indisvalid"
)


def ensure_index(conninfo: str, spec: VectorIndexSpec) -> str:
    """Return "exists" or "created"."""
    with psycopg.connect(conninfo, autocommit=True) as conn:
        if conn.execute(_INVALID, (spec.index_name,)).fetchone():
            _log.warning("dropping_invalid_index", extra={"ctx": {"index": spec.index_name}})
            conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS rag.{spec.index_name}")
        before = conn.execute("SELECT to_regclass(%s)", (f"rag.{spec.index_name}",)).fetchone()
        conn.execute(spec.create_index_sql())
    return "exists" if before and before[0] else "created"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--space", required=True)
    parser.add_argument("--dimensions", type=int, required=True)
    parser.add_argument("--metric", choices=["cosine", "inner_product", "l2"], default="cosine")
    parser.add_argument("--m", type=int, default=16)
    parser.add_argument("--ef-construction", type=int, default=64)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    settings = Settings()
    if settings.migration_database_url is None:
        print("RAG_MIGRATION_DATABASE_URL is not set", file=sys.stderr)
        return 2
    try:
        spec = VectorIndexSpec(
            space=args.space,
            dimensions=args.dimensions,
            metric=args.metric,
            m=args.m,
            ef_construction=args.ef_construction,
        )
    except IndexSpecError as exc:
        print(f"invalid index spec: {exc}", file=sys.stderr)
        return 2
    result = ensure_index(settings.migration_database_url.get_secret_value(), spec)
    print(f"{result}: {spec.index_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
