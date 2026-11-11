"""Print the shell commands that export the database test variables from reference-implementation/.env.

    python scripts/pg_test_env.py                  # PowerShell syntax (default)
    python scripts/pg_test_env.py --shell bash     # bash/zsh syntax; use:  eval "$(python scripts/pg_test_env.py --shell bash)"

The passwords are read from your local, git-ignored .env and printed to YOUR terminal only. They are
needed by the integration tests that create scratch databases and log in as rag_owner and rag_app.
"""

from __future__ import annotations

import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    if not ENV.exists():
        print(
            "no .env file: copy .env.example to .env and set the passwords first",
            file=sys.stderr,
        )
        return 1
    env = read_env()
    port = env.get("POSTGRES_HOST_PORT", "5433")
    user, db = env.get("POSTGRES_USER", "rag"), env.get("POSTGRES_DB", "rag")
    pairs = {
        "RAG_TEST_ADMIN_URL": f"postgresql://{user}:{env['POSTGRES_PASSWORD']}@127.0.0.1:{port}/{db}",
        "RAG_TEST_OWNER_PASSWORD": env["RAG_OWNER_PASSWORD"],
        "RAG_TEST_APP_PASSWORD": env["RAG_APP_PASSWORD"],
        "RAG_TEST_WORKER_PASSWORD": env["RAG_WORKER_PASSWORD"],
        "RAG_TEST_DATABASE_URL": f"postgresql://rag_app:{env['RAG_APP_PASSWORD']}@127.0.0.1:{port}/{db}",
    }
    bash = "--shell" in sys.argv and sys.argv[sys.argv.index("--shell") + 1] == "bash"
    for key, value in pairs.items():
        print(f"export {key}='{value}'" if bash else f"$env:{key} = '{value}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
