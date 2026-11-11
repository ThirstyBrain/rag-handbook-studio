"""Measured benchmark of pgvector HNSW behaviour on the development database (Chapter 20).

What it measures, on SYNTHETIC clustered vectors (not real embeddings, so absolute numbers do not transfer):
  1. exact (sequential scan) latency, and HNSW recall@10 and latency against exact results for several ef_search values;
  2. index build time and size, for `vector` and for a `halfvec` expression index;
  3. filtered search: how many rows an approximate index returns when a WHERE filter keeps 10% or 1% of rows,
     with and without hnsw.iterative_scan (the behaviour described in the pgvector README).

Method: one connection, queries run one at a time (no concurrency), 200 held-out queries drawn from the same
mixture, each setting preceded by a warm-up pass. Latencies include client round trips through the Docker
port mapping on this host. Ground truth is computed with no vector index present (exact by construction).
This is a measurement on one machine on one day, not a benchmark of any product.

Needs the compose database and RAG_TEST_ADMIN_URL (python scripts/pg_test_env.py). Run from
reference-implementation/backend:   python ../evaluation/bench_pgvector.py [--n 30000] [--dim 128]
It creates and drops its own scratch database and writes results/bench-pgvector-<date>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg

K = 10
EF_VALUES = (10, 20, 40, 100, 200, 400)
RESULTS = Path(__file__).resolve().parent / "results"


def vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.5f}" for v in values) + "]"


def make_data(n: int, dim: int, queries: int, seed: int) -> tuple[list[list[float]], list[list[float]]]:
    rng = random.Random(seed)
    centers = [[rng.gauss(0, 1.0) for _ in range(dim)] for _ in range(50)]

    def point() -> list[float]:
        c = centers[rng.randrange(len(centers))]
        return [x + rng.gauss(0, 0.35) for x in c]

    return [point() for _ in range(n)], [point() for _ in range(queries)]


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))]


def timed(conn: psycopg.Connection[Any], sql: str, params: tuple[Any, ...]) -> tuple[list[int], float]:
    t0 = time.perf_counter()
    rows = conn.execute(sql, params).fetchall()  # type: ignore[call-overload]
    return [r[0] for r in rows], (time.perf_counter() - t0) * 1000


def run_set(conn: psycopg.Connection[Any], sql: str, qs: list[str], truth: list[set[int]]) -> dict[str, float]:
    for q in qs[:20]:  # warm-up, not counted
        conn.execute(sql, (q,)).fetchall()  # type: ignore[call-overload]
    lat, recalls, counts = [], [], []
    for q, gt in zip(qs, truth, strict=True):
        ids, ms = timed(conn, sql, (q,))
        lat.append(ms)
        counts.append(len(ids))
        recalls.append(len(gt & set(ids)) / len(gt) if gt else 1.0)
    return {
        "recall_at_10": round(statistics.mean(recalls), 4),
        "rows_returned_mean": round(statistics.mean(counts), 2),
        "latency_ms_p50": round(pct(lat, 0.5), 2),
        "latency_ms_p95": round(pct(lat, 0.95), 2),
    }


def with_db(admin_url: str, name: str) -> str:
    p = urlsplit(admin_url)
    return urlunsplit((p.scheme, p.netloc, f"/{name}", "", ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30_000)
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    admin = os.environ.get("RAG_TEST_ADMIN_URL")
    if not admin:
        print("set RAG_TEST_ADMIN_URL first (python scripts/pg_test_env.py)")
        return 2
    name = f"bench_{uuid.uuid4().hex[:8]}"
    n, dim = args.n, args.dim
    out: dict[str, Any] = {
        "date": date.today().isoformat(),
        "host": {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count()},
        "params": {"n": n, "dim": dim, "queries": args.queries, "k": K, "seed": args.seed,
                   "data": "50-cluster Gaussian mixture (std 0.35), synthetic", "metric": "L2"},
    }
    with psycopg.connect(admin, autocommit=True) as a:
        a.execute(f'CREATE DATABASE "{name}"')
    try:
        with psycopg.connect(with_db(admin, name), autocommit=True) as c:
            c.execute("CREATE EXTENSION vector")
            out["versions"] = {
                "postgres": c.execute("SHOW server_version").fetchone()[0],  # type: ignore[index]
                "pgvector": c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0],  # type: ignore[index]
            }
            data, queries = make_data(n, dim, args.queries, args.seed)
            qs = [vec(q) for q in queries]
            c.execute(f"CREATE TABLE items (id int PRIMARY KEY, bucket int, category int, embedding vector({dim}))")
            rng = random.Random(args.seed + 1)
            t0 = time.perf_counter()
            with c.cursor() as cur, cur.copy("COPY items (id, bucket, category, embedding) FROM STDIN") as cp:
                for i, v in enumerate(data):
                    cp.write_row((i, i % 10, rng.randrange(100), vec(v)))
            c.execute("ANALYZE items")
            out["load_s"] = round(time.perf_counter() - t0, 2)
            out["table_bytes"] = c.execute("SELECT pg_table_size('items')").fetchone()[0]  # type: ignore[index]

            order = "ORDER BY embedding <-> %s::vector LIMIT 10"
            base = f"SELECT id FROM items {order}"
            filt10 = f"SELECT id FROM items WHERE bucket = 3 {order}"  # keeps 10% of rows
            filt1 = f"SELECT id FROM items WHERE category = 7 {order}"  # keeps about 1% of rows
            # ground truth BEFORE any vector index exists: exact by construction
            truth = [set(timed(c, base, (q,))[0]) for q in qs]
            truth10 = [set(timed(c, filt10, (q,))[0]) for q in qs]
            truth1 = [set(timed(c, filt1, (q,))[0]) for q in qs]
            out["exact"] = run_set(c, base, qs, truth)

            c.execute("SET maintenance_work_mem = '128MB'")
            # The compose database container has Docker's default 64 MB /dev/shm: a parallel build needs shared
            # memory of about maintenance_work_mem and failed with "No space left on device" (finding, Chapter 20).
            c.execute("SET max_parallel_maintenance_workers = 0")
            t0 = time.perf_counter()
            c.execute("CREATE INDEX items_hnsw ON items USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64)")
            out["hnsw_vector"] = {
                "build_s": round(time.perf_counter() - t0, 2),
                "index_bytes": c.execute("SELECT pg_relation_size('items_hnsw')").fetchone()[0],  # type: ignore[index]
                "maintenance_work_mem": "128MB", "max_parallel_maintenance_workers": 0, "m": 16, "ef_construction": 64,
            }
            plan = c.execute("EXPLAIN " + base.replace("%s", f"'{qs[0]}'")).fetchall()  # type: ignore[call-overload]
            out["hnsw_vector"]["plan_uses_hnsw"] = any("items_hnsw" in r[0] for r in plan)
            sweep = {}
            for ef in EF_VALUES:
                c.execute(f"SET hnsw.ef_search = {ef}")
                sweep[str(ef)] = run_set(c, base, qs, truth)
            out["hnsw_vector"]["ef_search_sweep"] = sweep
            c.execute("SET hnsw.ef_search = 40")

            # halfvec expression index
            hbase = f"SELECT id FROM items ORDER BY embedding::halfvec({dim}) <-> %s::halfvec({dim}) LIMIT 10"
            t0 = time.perf_counter()
            c.execute(f"CREATE INDEX items_half ON items USING hnsw ((embedding::halfvec({dim})) halfvec_l2_ops) WITH (m = 16, ef_construction = 64)")
            half: dict[str, Any] = {
                "build_s": round(time.perf_counter() - t0, 2),
                "index_bytes": c.execute("SELECT pg_relation_size('items_half')").fetchone()[0],  # type: ignore[index]
            }
            hplan = c.execute("EXPLAIN " + hbase.replace("%s", f"'{qs[0]}'")).fetchall()  # type: ignore[call-overload]
            half["plan_uses_halfvec_index"] = any("items_half" in r[0] for r in hplan)
            half["ef_search_sweep"] = {}
            for ef in (40, 100):
                c.execute(f"SET hnsw.ef_search = {ef}")
                half["ef_search_sweep"][str(ef)] = run_set(c, hbase, qs, truth)
            out["hnsw_halfvec"] = half
            c.execute("SET hnsw.ef_search = 40")

            # filtered search with the vector index, ef_search = 40 (the default)
            filtered: dict[str, Any] = {}
            for label, sql, gt in (("filter_10pct", filt10, truth10), ("filter_1pct", filt1, truth1)):
                res: dict[str, Any] = {}
                for mode in ("off", "relaxed_order"):
                    c.execute(f"SET hnsw.iterative_scan = {mode}")
                    c.execute("SET enable_seqscan = off")  # force the index path so the README scenario is exercised
                    res[f"index_forced_iterative_{mode}"] = run_set(c, sql, qs, gt)
                    c.execute("RESET enable_seqscan")
                c.execute("SET hnsw.iterative_scan = off")
                res["planner_default"] = run_set(c, sql, qs, gt)
                p = c.execute("EXPLAIN " + sql.replace("%s", f"'{qs[0]}'")).fetchall()  # type: ignore[call-overload]
                res["planner_default_plan_first_line"] = p[0][0]
                filtered[label] = res
            out["filtered"] = filtered
    finally:
        with psycopg.connect(admin, autocommit=True) as a:
            a.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"bench-pgvector-{out['date']}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("written:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
