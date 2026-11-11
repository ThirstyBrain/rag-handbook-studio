"""Mutation check for the LLM gateway's policy code.

Applies one small defect at a time to the source, runs the gateway unit tests, expects them to FAIL
(mutant killed), and always restores the original file. Run from reference-implementation/backend:
    python ../scripts/mutation_llm.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
SRC = BACKEND / "src" / "rag_service" / "features" / "llm"
TESTS = [
    "../tests/unit/test_llm_gateway.py",
    "../tests/unit/test_llm_adapters.py",
    "../tests/unit/test_llm_config.py",
]

# (file, original text, mutated text, description)
MUTANTS: list[tuple[str, str, str, str]] = [
    (
        "gateway.py",
        "sensitivity is Sensitivity.RESTRICTED and provider.locality",
        "False and provider.locality",
        "restricted data may reach external providers",
    ),
    (
        "gateway.py",
        "if request.max_output_tokens <= route.max_output_tokens:",
        "if True:",
        "route token cap not enforced",
    ),
    (
        "gateway.py",
        "not provider.supports_temperature",
        "False",
        "temperature sent to providers that reject it",
    ),
    (
        "gateway.py",
        "if not (err.fallback or err.retryable):",
        "if False:",
        "invalid requests are retried and forwarded",
    ),
    (
        "gateway.py",
        "self._failures >= self._threshold",
        "self._failures > self._threshold",
        "breaker opens one failure late",
    ),
    (
        "gateway.py",
        "elif self._ledger.spent_today >= budget:",
        "elif False:",
        "daily budget ignored",
    ),
    (
        "gateway.py",
        "delay = max(delay, min(err.retry_after_s, cfg.cap_s))",
        "delay = max(delay, err.retry_after_s)",
        "retry-after not capped",
    ),
    (
        "gateway.py",
        "if started_yield:",
        "if False:",
        "stream falls back after text was already sent",
    ),
    (
        "gateway.py",
        "if not self._price_known(target):",
        "if False:",
        "unpriced external spend allowed under a budget",
    ),
    (
        "gateway.py",
        'if provider.locality == "external":\n            self._ledger.add(cost)',
        "if False:\n            self._ledger.add(cost)",
        "external spend never recorded",
    ),
    (
        "gateway.py",
        "if len(request.inputs) > route.max_batch:",
        "if False:",
        "embedding batch limit not enforced",
    ),
    (
        "gateway.py",
        "if len(dims) != 1:",
        "if False:",
        "inconsistent embedding dimensions accepted",
    ),
    ("config.py", "len(spaces) != 1", "False", "embed route may mix embedding spaces"),
    (
        "providers/openai_compat.py",
        'raise TargetUnsupported(\n            f"target does not support',
        'raise ProviderUnavailable(\n            f"target does not support',
        "unsupported target (404/501) retried instead of falling back",
    ),
    (
        "providers/anthropic.py",
        'if result.finish_reason == "refusal":\n            raise ContentRefused',
        "if False:\n            raise ContentRefused",
        "Claude refusals returned as normal text",
    ),
]


def run_tests() -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-c", "pyproject.toml", *TESTS]
    return subprocess.run(cmd, cwd=BACKEND, capture_output=True, check=False).returncode == 0  # noqa: S603


def main() -> int:
    if not run_tests():
        print("baseline tests fail: fix them before mutation testing")
        return 2
    survived: list[str] = []
    for filename, original, mutated, description in MUTANTS:
        path = SRC / filename
        source = path.read_text(encoding="utf-8")
        if original not in source:
            print(f"SKIPPED (pattern not found): {description}")
            survived.append(f"pattern missing: {description}")
            continue
        try:
            path.write_text(source.replace(original, mutated, 1), encoding="utf-8")
            killed = not run_tests()
        finally:
            path.write_text(source, encoding="utf-8")
        print(f"{'killed  ' if killed else 'SURVIVED'}  {filename}: {description}")
        if not killed:
            survived.append(description)
    print(f"\n{len(MUTANTS) - len(survived)}/{len(MUTANTS)} mutants killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
