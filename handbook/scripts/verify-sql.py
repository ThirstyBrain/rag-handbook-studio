"""Run the handbook's SQL verification suite against a throw-away PostgreSQL + pgvector container.

Usage:  python -I scripts/verify-sql.py [--keep]

What it does
  1. Requires a running Docker daemon (exit code 2 otherwise).
  2. Builds the image from scripts/verify-sql/Dockerfile if absent (pgvector v0.8.7 on a digest-pinned
     postgres:16-alpine base).
  3. Starts a container with NO published ports and a random password (used only via `docker exec`).
  4. Runs every scripts/verify-sql/NN-*.sql with psql -v ON_ERROR_STOP=1. Assertions inside the SQL
     RAISE EXCEPTION on failure; NOTICE lines carry the measurements the chapters quote.
  5. Removes the container (unless --keep) and exits 0 only if every file passed.

These checks verify documented behaviour of pgvector/PostgreSQL and the handbook's illustrative SQL.
Measurements are on small synthetic datasets and are NOT performance benchmarks.
"""
from __future__ import annotations

import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "scripts" / "verify-sql"
IMAGE = "rag-handbook-sql-verify:pg16-pgvector-0.8.7"
NAME = "rag-handbook-sql-verify"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, **kw)


def txt(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def main() -> int:
    keep = "--keep" in sys.argv
    info = run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if info.returncode != 0:
        print("Docker daemon not available. Start Docker Desktop and retry.", file=sys.stderr)
        return 2
    print(f"docker server {txt(info.stdout).strip()}")

    if run(["docker", "image", "inspect", IMAGE]).returncode != 0:
        print(f"building {IMAGE} ...")
        b = run(["docker", "build", "-t", IMAGE, str(SQL_DIR)])
        if b.returncode != 0:
            print(txt(b.stderr)[-2000:], file=sys.stderr)
            return 2

    run(["docker", "rm", "-f", NAME])
    pw = secrets.token_urlsafe(18)
    started = run(["docker", "run", "-d", "--name", NAME, "--memory", "1g", "-e", f"POSTGRES_PASSWORD={pw}", IMAGE])
    if started.returncode != 0:
        print(txt(started.stderr), file=sys.stderr)
        return 2
    failures = 0
    try:
        for _ in range(60):
            if run(["docker", "exec", NAME, "pg_isready", "-U", "postgres"]).returncode == 0:
                break
            time.sleep(1)
        else:
            print("postgres did not become ready", file=sys.stderr)
            return 2
        time.sleep(1)  # entrypoint restarts once after init scripts; wait for the final server
        for _ in range(30):
            if run(["docker", "exec", NAME, "psql", "-U", "postgres", "-At", "-c", "select 1"]).returncode == 0:
                break
            time.sleep(1)
        ext = run(["docker", "exec", NAME, "psql", "-U", "postgres", "-X", "-q", "-c", "CREATE EXTENSION IF NOT EXISTS vector"])
        if ext.returncode != 0:
            print(txt(ext.stderr), file=sys.stderr)
            return 2
        ver = run(["docker", "exec", NAME, "psql", "-U", "postgres", "-At", "-c",
                   "select version() || ' | pgvector ' || (select extversion from pg_extension where extname='vector')"])
        print(txt(ver.stdout).strip())

        for f in sorted(SQL_DIR.glob("[0-9][0-9]-*.sql")):
            t0 = time.time()
            r = run(["docker", "exec", "-i", NAME, "psql", "-U", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=1"],
                    input=f.read_bytes())
            ok = r.returncode == 0
            failures += not ok
            print(f"\n{'PASS' if ok else 'FAIL'}  {f.name}  ({time.time() - t0:.1f}s)")
            for line in txt(r.stderr).splitlines():
                if line.startswith(("NOTICE:", "ERROR:", "DETAIL:", "CONTEXT:", "HINT:")) and "does not exist, skipping" not in line:
                    print("   ", line.replace("NOTICE:  ", "").strip())
    finally:
        if not keep:
            run(["docker", "rm", "-f", NAME])
    print(f"\n{'ALL PASSED' if failures == 0 else f'{failures} FILE(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
