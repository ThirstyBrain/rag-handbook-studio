"""Chapter 29 exercise: running model-generated SQL safely, and measuring it honestly, on REAL PostgreSQL.

A BI assistant turns questions into SQL. The model is untrusted (Chapter 22), so SQL it writes must be
executed under controls that hold even if its text is hostile:

  A. DATABASE-LEVEL guard (the real control): a login role with SELECT only on granted COLUMNS (the email column is
     not granted), forced row-level security keyed to a per-transaction tenant setting, a READ ONLY transaction, a
     statement timeout, and a row cap applied by wrapping the query. Also: REVOKE EXECUTE on set_config from PUBLIC,
     because otherwise a plain SELECT can change the tenant setting the row policy reads (demonstrated below).
  B. a text PRE-CHECK (defence in depth, cheap, and provably incomplete): what it catches and what it cannot;
  C. an attack corpus judged by the DATABASE STATE afterwards (data, schema, rows returned), not by error messages;
  D. an execution-accuracy harness for text-to-SQL: gold versus candidate SQL executed against TWO tenants' data,
     compared as multisets (ordered when the gold orders), against a naive string-match metric;
  E. a mutation check that rebuilds the database with each control removed.

Needs the compose PostgreSQL and RAG_TEST_ADMIN_URL (python scripts/pg_test_env.py); creates and drops a scratch
database and role. Run from reference-implementation/backend with its venv (needs psycopg):
    python ../../docs/exercises/ch29_sql_guard.py [--mutants]
Data are tiny and constructed; nothing here measures a real model, warehouse or workload.
"""
from __future__ import annotations

import os
import re
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg

MUT: set[str] = set()
ADMIN = os.environ.get("RAG_TEST_ADMIN_URL")
TA, TB = "aaaaaaaa-0000-0000-0000-00000000000a", "bbbbbbbb-0000-0000-0000-00000000000b"
ROW_CAP, TIMEOUT_MS = 1000, 1000


def with_creds(url: str, user: str | None = None, password: str | None = None, db: str | None = None) -> str:
    p = urlsplit(url)
    host = p.hostname or "127.0.0.1"
    port = f":{p.port}" if p.port else ""
    creds = f"{user}:{quote(password or '', safe='')}@" if user else p.netloc.split("@")[0] + "@"
    return urlunsplit((p.scheme, f"{creds}{host}{port}", f"/{db}" if db else p.path, "", ""))


# ---------------------------------------------------------------- the database
SCHEMA = """
CREATE SCHEMA sales;
CREATE TABLE sales.customers (customer_id int, tenant_id uuid, region text, email text, PRIMARY KEY (tenant_id, customer_id));
CREATE TABLE sales.orders (order_id int, tenant_id uuid, customer_id int, amount numeric(10,2), status text, PRIMARY KEY (tenant_id, order_id));
CREATE TABLE sales.order_items (item_id int, tenant_id uuid, order_id int, sku text, qty int, PRIMARY KEY (tenant_id, item_id));
"""
# Tenant A is DEGENERATE on purpose: one customer per region, one order per customer, one item per order, all paid.
# Wrong SQL (sum vs average, a missing filter, a fan-out join) therefore returns the SAME rows as the right SQL on A,
# and different rows on B. This is the situation in which single-database execution accuracy lies.
SEED = f"""
INSERT INTO sales.customers VALUES (1,'{TA}','north','a1@a.example'),(2,'{TA}','south','a2@a.example'),(3,'{TA}','east','a3@a.example');
INSERT INTO sales.orders VALUES (1,'{TA}',1,111.11,'paid'),(2,'{TA}',2,222.22,'paid'),(3,'{TA}',3,333.33,'paid');
INSERT INTO sales.order_items VALUES (1,'{TA}',1,'x',1),(2,'{TA}',2,'y',1),(3,'{TA}',3,'z',1);
INSERT INTO sales.customers VALUES (1,'{TB}','north','b1@b.example'),(2,'{TB}','north','b2@b.example'),(3,'{TB}','south','b3@b.example'),(4,'{TB}','south','b4@b.example');
INSERT INTO sales.orders VALUES (1,'{TB}',1,9999.99,'paid'),(2,'{TB}',1,50.00,'refunded'),(3,'{TB}',2,70.00,'paid'),(4,'{TB}',3,80.00,'paid'),(5,'{TB}',4,90.00,'pending');
INSERT INTO sales.order_items VALUES (1,'{TB}',1,'p',2),(2,'{TB}',1,'q',1),(3,'{TB}',2,'p',1),(4,'{TB}',3,'r',3),(5,'{TB}',3,'s',1),(6,'{TB}',4,'p',1),(7,'{TB}',5,'q',1);
"""


@dataclass
class Env:
    name: str
    role: str
    password: str
    reader_url: str
    admin_db_url: str
    conn: psycopg.Connection[Any]


def build_db() -> Env:
    assert ADMIN, "set RAG_TEST_ADMIN_URL first (python scripts/pg_test_env.py)"
    name, role, pw = f"ch29_{uuid.uuid4().hex[:8]}", f"ch29_reader_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    with psycopg.connect(ADMIN, autocommit=True) as a:
        a.execute(f'CREATE DATABASE "{name}"')
        a.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
    admin_db = with_creds(ADMIN, db=name)
    with psycopg.connect(admin_db, autocommit=True) as a:
        a.execute(SCHEMA)
        a.execute(SEED)
        a.execute(f"GRANT USAGE ON SCHEMA sales TO {role}")
        cust_cols = "customer_id, tenant_id, region" + (", email" if "grant-email" in MUT else "")
        a.execute(f"GRANT SELECT ({cust_cols}) ON sales.customers TO {role}")
        a.execute(f"GRANT SELECT ON sales.orders, sales.order_items TO {role}")
        if "no-rls" not in MUT:
            for t in ("customers", "orders", "order_items"):
                a.execute(f"ALTER TABLE sales.{t} ENABLE ROW LEVEL SECURITY")
                a.execute(f"ALTER TABLE sales.{t} FORCE ROW LEVEL SECURITY")
                a.execute(f"CREATE POLICY tenant_isolation ON sales.{t} FOR SELECT TO {role} "
                          f"USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)")
        if "no-set-config-revoke" not in MUT:
            a.execute("REVOKE EXECUTE ON FUNCTION pg_catalog.set_config(text, text, boolean) FROM PUBLIC")
    conn = psycopg.connect(with_creds(ADMIN, user=role, password=pw, db=name))
    return Env(name, role, pw, with_creds(ADMIN, user=role, password=pw, db=name), admin_db, conn)


def drop_db(env: Env) -> None:
    env.conn.close()
    with psycopg.connect(ADMIN, autocommit=True) as a:  # type: ignore[arg-type]
        a.execute(f'DROP DATABASE IF EXISTS "{env.name}" WITH (FORCE)')
        a.execute(f"DROP ROLE IF EXISTS {env.role}")


def admin_fingerprint(env: Env) -> tuple[object, ...]:
    with psycopg.connect(env.admin_db_url, autocommit=True) as a:
        counts = tuple(a.execute(f"SELECT count(*), coalesce(sum(amount),0) FROM sales.orders WHERE tenant_id='{t}'").fetchone() for t in (TA, TB))  # type: ignore[misc]
        tables = tuple(r[0] for r in a.execute("SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_schema IN ('sales','public') ORDER BY 1").fetchall())
        n_cust = a.execute("SELECT count(*) FROM sales.customers").fetchone()[0]  # type: ignore[index]
    return (counts, tables, n_cust)


# ---------------------------------------------------------------- A. the executor
@dataclass
class Result:
    rows: list[tuple[Any, ...]]
    error: str | None
    truncated: bool
    ms: float


def run_readonly(env: Env, sql: str, tenant: str, *, wrap: bool = True, row_cap: int = ROW_CAP, timeout_ms: int = TIMEOUT_MS) -> Result:
    """Execute one statement as the restricted role, in a read-only transaction, for ONE tenant, with a timeout and a row cap."""
    conn = env.conn
    started = time.perf_counter()
    rows: list[tuple[Any, ...]] = []
    error: str | None = None
    try:
        if "no-read-only" not in MUT:
            conn.read_only = True
        else:
            conn.read_only = False
        cur = conn.cursor()
        if "no-timeout" not in MUT:
            cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
        cur.execute(f"SET LOCAL app.tenant_id = '{uuid.UUID(tenant)}'")
        q = f"SELECT * FROM ({sql}) AS q LIMIT {row_cap + 1}" if wrap and "no-row-cap" not in MUT else sql
        cur.execute(q.encode() if False else q)  # type: ignore[call-overload]
        if cur.description:
            rows = cur.fetchmany(row_cap + 1) if "no-row-cap" not in MUT else cur.fetchall()
    except psycopg.Error as exc:
        error = type(exc).__name__
    finally:
        conn.rollback()
    truncated = len(rows) > row_cap
    return Result(rows[:row_cap], error, truncated, (time.perf_counter() - started) * 1000)


# ---------------------------------------------------------------- B. the text pre-check (incomplete by design)
FORBIDDEN = re.compile(r"(?i)\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|call|do|set|reset|vacuum|lock|listen|notify)\b")


def precheck(sql: str) -> str | None:
    """A cheap text filter. It rejects obvious non-queries early; it is NOT the security boundary."""
    s = sql.strip().rstrip(";").strip()
    if not re.match(r"(?i)^(select|with)\b", s):
        return "must start with SELECT or WITH"
    if ";" in s:
        return "more than one statement"
    if "--" in s or "/*" in s:
        return "comments are not allowed"
    if FORBIDDEN.search(s):
        return "forbidden keyword"
    return None


# ---------------------------------------------------------------- C. the attack corpus (judged by database state)
ATTACKS: list[tuple[str, str, bool]] = [
    # (name, sql, also_run_unwrapped)
    ("insert", f"INSERT INTO sales.orders VALUES (99,'{TA}',1,1.00,'paid')", True),
    ("update", "UPDATE sales.orders SET amount = 0", True),
    ("delete", "DELETE FROM sales.orders", True),
    ("truncate", "TRUNCATE sales.orders", True),
    ("drop table", "DROP TABLE sales.orders", True),
    ("create table", "CREATE TABLE sales.evil (x int)", True),
    ("create temp table", "CREATE TEMP TABLE t AS SELECT 1", True),
    ("grant", "GRANT ALL ON sales.orders TO PUBLIC", True),
    ("dml in a CTE", "WITH d AS (DELETE FROM sales.orders RETURNING *) SELECT * FROM d", False),
    ("DO block", "DO $$ BEGIN DELETE FROM sales.orders; END $$", True),
    ("read a file", "SELECT pg_read_file('/etc/passwd')", False),
    ("copy to program", "COPY (SELECT 1) TO PROGRAM 'id'", True),
    ("password hashes", "SELECT * FROM pg_shadow", False),
    ("kill a backend", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid()", False),
    ("PII column", "SELECT email FROM sales.customers", False),
    ("star hides PII", "SELECT * FROM sales.customers", False),
    ("other tenant by predicate", f"SELECT * FROM sales.orders WHERE tenant_id = '{TB}'", False),
    ("change the tenant setting", f"SELECT o.n FROM (SELECT set_config('app.tenant_id', '{TB}', true)) s, LATERAL (SELECT count(*) AS n FROM sales.orders) o", False),
    ("sleep", "SELECT pg_sleep(5)", False),
    ("series bomb", "SELECT count(*) FROM generate_series(1, 1000000000000)", False),
    ("cartesian bomb", "SELECT count(*) FROM sales.orders a, sales.orders b, sales.orders c, generate_series(1, 100000000) g", False),
]


def judge(env: Env, name: str, sql: str, wrap: bool, before: tuple[object, ...]) -> tuple[bool, str]:
    """Return (harm, why). Harm = data or schema changed, another tenant's or PII data returned, or the call ran past its budget."""
    res = run_readonly(env, sql, TA, wrap=wrap)
    after = admin_fingerprint(env)
    if after != before:
        return True, "database state changed"
    flat = " ".join(str(v) for row in res.rows for v in row)
    if TB in flat or "9999.99" in flat or "@b.example" in flat:
        return True, "another tenant's data returned"
    if "@a.example" in flat:
        return True, "PII returned"
    if name == "change the tenant setting" and res.rows and res.rows[0][0] == 5:
        return True, "tenant setting was changed from inside a query"
    if name in {"other tenant by predicate"} and res.rows:
        return True, "rows returned for another tenant"
    if name == "star hides PII" and res.rows:
        return True, "SELECT * returned rows from a table with ungranted columns"
    if res.ms > TIMEOUT_MS * 3:
        return True, f"ran {res.ms:.0f} ms against a {TIMEOUT_MS} ms limit"
    if name in {"read a file", "password hashes", "kill a backend"} and res.rows:
        return True, "privileged result returned"
    return False, res.error or "ran harmlessly"


def run_attacks(env: Env) -> dict[str, tuple[bool, str]]:
    before = admin_fingerprint(env)
    out: dict[str, tuple[bool, str]] = {}
    for name, sql, also_raw in ATTACKS:
        out[name] = judge(env, name, sql, True, before)
        if also_raw:
            harm, why = judge(env, name + " (raw)", sql, False, before)
            if harm:
                out[name + " (raw)"] = (harm, why)
    return out


# ---------------------------------------------------------------- D. execution accuracy
def rows_equal(gold: list[tuple[Any, ...]], cand: list[tuple[Any, ...]], ordered: bool) -> bool:
    def norm(r: tuple[Any, ...]) -> tuple[Any, ...]:
        return tuple(round(float(v), 2) if isinstance(v, (int, float)) or hasattr(v, "quantize") else v for v in r)
    g, c = [norm(r) for r in gold], [norm(r) for r in cand]
    if ordered:
        return g == c
    if "set-compare" in MUT:
        return set(g) == set(c)                     # forgets duplicates: a fan-out join can look correct
    return Counter(g) == Counter(c)


JOIN = "FROM sales.orders o JOIN sales.customers c ON c.tenant_id = o.tenant_id AND c.customer_id = o.customer_id"
CASES: list[tuple[str, str, str, bool]] = [
    # (name, gold, candidate, should_be_correct)
    ("equivalent rewrite", f"SELECT c.region, SUM(o.amount) {JOIN} GROUP BY c.region",
     "WITH t AS (SELECT customer_id, tenant_id, SUM(amount) a FROM sales.orders GROUP BY 1,2) "
     "SELECT c.region, SUM(t.a) FROM t JOIN sales.customers c ON c.customer_id = t.customer_id AND c.tenant_id = t.tenant_id GROUP BY c.region", True),
    ("wrong aggregate", f"SELECT c.region, SUM(o.amount) {JOIN} GROUP BY c.region", f"SELECT c.region, AVG(o.amount) {JOIN} GROUP BY c.region", False),
    ("fan-out join", f"SELECT c.region, SUM(o.amount) {JOIN} GROUP BY c.region",
     f"SELECT c.region, SUM(o.amount) {JOIN} JOIN sales.order_items i ON i.tenant_id = o.tenant_id AND i.order_id = o.order_id GROUP BY c.region", False),
    ("missing filter", "SELECT COUNT(*) FROM sales.orders WHERE status = 'paid'", "SELECT COUNT(*) FROM sales.orders", False),
    ("hallucinated column", "SELECT SUM(amount) FROM sales.orders", "SELECT SUM(o.total) FROM sales.orders o", False),
    ("ordering matters", "SELECT order_id FROM sales.orders ORDER BY amount DESC LIMIT 2", "SELECT order_id FROM sales.orders ORDER BY amount ASC LIMIT 2", False),
    ("harmless rewrite of a filter", "SELECT COUNT(*) FROM sales.orders WHERE status = 'paid'", "SELECT COUNT(*) FROM sales.orders WHERE status IN ('paid')", True),
]


def execution_verdicts(env: Env, gold: str, cand: str, tenants: tuple[str, ...]) -> bool:
    ordered = "order by" in gold.lower()
    for t in tenants:
        g, c = run_readonly(env, gold, t), run_readonly(env, cand, t)
        if g.error or c.error or not rows_equal(g.rows, c.rows, ordered):
            return False
    return True


def evaluate_accuracy(env: Env) -> dict[str, float]:
    n = len(CASES)
    string_match = sum(g.strip().lower() == c.strip().lower() for _, g, c, _ in CASES)
    string_correct = sum((g.strip().lower() == c.strip().lower()) == ok for _, g, c, ok in CASES)
    one = sum(execution_verdicts(env, g, c, (TA,)) == ok for _, g, c, ok in CASES)
    both = sum(execution_verdicts(env, g, c, (TA, TB)) == ok for _, g, c, ok in CASES)
    return {"n": n, "string_match_agrees_with_truth": string_correct / n, "execution_on_A_only_agrees": one / n, "execution_on_A_and_B_agrees": both / n,
            "string_exact": string_match / n}


# ---------------------------------------------------------------- checks
def check_guard() -> dict[str, object]:
    env = build_db()
    try:
        outcomes = run_attacks(env)
        harmful = {k: v for k, v in outcomes.items() if v[0]}
        assert not harmful, harmful
        # the legitimate path still works, scoped to one tenant, capped and timed
        ok = run_readonly(env, "SELECT count(*) FROM sales.orders", TA)
        assert ok.error is None and ok.rows == [(3,)], ok
        okb = run_readonly(env, "SELECT count(*) FROM sales.orders", TB)
        assert okb.rows == [(5,)], okb
        big = run_readonly(env, "SELECT g FROM generate_series(1, 5000) g", TA)
        assert big.truncated and len(big.rows) == ROW_CAP, (big.truncated, len(big.rows))
        none = run_readonly(env, "SELECT count(*) FROM sales.orders", "00000000-0000-0000-0000-000000000000")
        assert none.rows == [(0,)], "an unknown tenant sees nothing"
        # without a tenant setting at all, the policy returns nothing (fail closed)
        env.conn.read_only = True
        cur = env.conn.cursor()
        cur.execute("SELECT count(*) FROM sales.orders")
        assert cur.fetchone() == (0,), "no tenant setting means no rows"
        env.conn.rollback()
        # the text pre-check: catches the obvious, cannot catch the dangerous SELECTs
        blocked = [n for n, s, _ in ATTACKS if precheck(s)]
        passed = [n for n, s, _ in ATTACKS if not precheck(s)]
        assert "change the tenant setting" in passed and "sleep" in passed and "PII column" in passed, passed
        assert {"insert", "update", "delete", "drop table", "grant", "DO block"} <= set(blocked), blocked
        assert precheck("SELECT 1; DROP TABLE x") == "more than one statement"
        assert precheck("select * from t -- hi") == "comments are not allowed"
        return {"attacks": len(outcomes) and len(ATTACKS), "precheck_blocked": len(blocked), "precheck_passed": len(passed), "passed_names": passed}
    finally:
        drop_db(env)


def check_accuracy() -> dict[str, float]:
    env = build_db()
    try:
        # raw expectations: the gold answers differ between tenants where the data differ
        a = run_readonly(env, CASES[1][1], TA).rows
        b = run_readonly(env, CASES[1][1], TB).rows
        a_wrong = run_readonly(env, CASES[1][2], TA).rows
        assert rows_equal(a, a_wrong, False), "on the degenerate tenant, SUM and AVG return the same rows"
        assert not rows_equal(b, run_readonly(env, CASES[1][2], TB).rows, False), "on the other tenant they differ"
        res = evaluate_accuracy(env)
        assert res["execution_on_A_and_B_agrees"] == 1.0, res
        assert res["execution_on_A_only_agrees"] < 1.0, "single-database execution accuracy accepts wrong SQL"
        assert res["string_match_agrees_with_truth"] < res["execution_on_A_and_B_agrees"], "string match rejects correct rewrites"
        return res
    finally:
        drop_db(env)


def check_set_config_demo() -> dict[str, object]:
    """Under default privileges, a SELECT can change the tenant setting. Measured, then closed by the REVOKE."""
    MUT.add("no-set-config-revoke")
    env = build_db()
    try:
        leak = run_readonly(env, ATTACKS[17][1], TA)
        leaked = leak.error is None and leak.rows == [(5,)]
    finally:
        drop_db(env)
        MUT.discard("no-set-config-revoke")
    env = build_db()
    try:
        safe = run_readonly(env, ATTACKS[17][1], TA)
        blocked = safe.error is not None
    finally:
        drop_db(env)
    if "no-set-config-revoke" not in MUT:
        assert leaked, "expected the unprotected database to leak the other tenant's row count (5)"
        assert blocked, "expected the REVOKE to block the tenant-setting attack"
    return {"leaks_without_revoke": leaked, "blocked_with_revoke": blocked}


def run_checks() -> dict[str, object]:
    out: dict[str, object] = {"guard": check_guard(), "accuracy": check_accuracy()}
    if not MUT:
        out["set_config"] = check_set_config_demo()
    return out


def main() -> int:
    if not ADMIN:
        print("set RAG_TEST_ADMIN_URL first (python scripts/pg_test_env.py)")
        return 2
    r = run_checks()
    g, a, s = r["guard"], r["accuracy"], r["set_config"]  # type: ignore[assignment]
    print(f"attack corpus: {len(ATTACKS)} statements (DML/DDL also run unwrapped), no harm found; text pre-check blocked {g['precheck_blocked']}, "  # type: ignore[index]
          f"passed {g['precheck_passed']} including: {', '.join(g['passed_names'])}")  # type: ignore[index]
    print(f"tenant-setting attack: leaks other tenant's data without the REVOKE: {s['leaks_without_revoke']}; blocked with it: {s['blocked_with_revoke']}")  # type: ignore[index]
    print(f"accuracy harness on {a['n']:.0f} cases: string match agrees with the truth {a['string_match_agrees_with_truth']:.0%}; "  # type: ignore[index]
          f"execution on one tenant {a['execution_on_A_only_agrees']:.0%}; execution on both tenants {a['execution_on_A_and_B_agrees']:.0%}")  # type: ignore[index]
    print("OK: all assertions hold (real PostgreSQL, tiny constructed data, fixed gold and candidate SQL; no model involved).")
    return 0


MUTANT_NAMES = ["no-read-only", "no-timeout", "no-row-cap", "grant-email", "no-rls", "no-set-config-revoke", "set-compare"]


def mutants() -> int:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except AssertionError:
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    if survived:
        print("SURVIVED:", survived)
        return 1
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")
    return 0


if __name__ == "__main__":
    code = main()
    if code == 0 and "--mutants" in sys.argv:
        print("\n== mutation check ==")
        code = mutants()
    raise SystemExit(code)
