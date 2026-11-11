"""One-command quality gate for the backend: lint, format check, type check, tests.

Usage (from reference-implementation/backend, inside the virtual environment):
    python ../scripts/check.py
Set RAG_TEST_DATABASE_URL to include the integration tests (see ../README.md).
The same command is what CI runs (component 20).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
STEPS: list[tuple[str, list[str]]] = [
    ("ruff lint", [sys.executable, "-m", "ruff", "check", ".", "../tests"]),
    (
        "ruff format",
        [sys.executable, "-m", "ruff", "format", "--check", ".", "../tests"],
    ),
    ("mypy (strict)", [sys.executable, "-m", "mypy"]),
    ("pytest", [sys.executable, "-m", "pytest", "-q"]),
]


def main() -> int:
    if "RAG_TEST_DATABASE_URL" not in os.environ:
        print(
            "note: RAG_TEST_DATABASE_URL not set; integration tests that need a database will be SKIPPED"
        )
    failed: list[str] = []
    for name, cmd in STEPS:
        print(f"\n== {name} ==", flush=True)
        if subprocess.run(cmd, cwd=BACKEND, check=False).returncode != 0:  # noqa: S603
            failed.append(name)
    print("\nFAILED: " + ", ".join(failed) if failed else "\nALL CHECKS PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
