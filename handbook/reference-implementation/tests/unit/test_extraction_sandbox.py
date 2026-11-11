"""The extraction sandbox: a real child process, and deliberately misbehaving children (ADR-016)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from rag_service.features.extraction.model import ExtractionLimits, Rejected
from rag_service.features.extraction.sandbox import SandboxedExtractor, SandboxUnavailable

CHILDREN = str(Path(__file__).parent / "sandbox_children")


def sandbox(module: str, **limits: object) -> SandboxedExtractor:
    return SandboxedExtractor(
        ExtractionLimits(**limits),  # type: ignore[arg-type]
        child_module=module,
        extra_python_paths=(CHILDREN,),
    )


# ------------------------------------------------------------------ the real child


def test_real_child_extracts_each_supported_text_type() -> None:
    box = SandboxedExtractor(ExtractionLimits())
    md = box.extract("text/markdown", b"# Title\n\nBody text here.\n")
    assert md.extractor == "markdown-1"
    assert [(b.kind, b.text, b.level) for b in md.blocks] == [
        ("heading", "Title", 1),
        ("paragraph", "Body text here.", 0),
    ]
    html = box.extract("text/html", b"<h2>Head</h2><p>Para <b>bold</b></p><script>x()</script>")
    assert [(b.kind, b.text) for b in html.blocks] == [
        ("heading", "Head"),
        ("paragraph", "Para bold"),
    ]


def test_real_child_reports_rejections_as_safe_codes() -> None:
    box = SandboxedExtractor(ExtractionLimits())
    with pytest.raises(Rejected) as info:
        box.extract("application/pdf", b"%PDF-1.4 this is not a pdf")
    assert info.value.reason == "malformed_pdf"
    with pytest.raises(Rejected) as info:
        box.extract("text/plain", b"   \n\n  ")
    assert info.value.reason == "no_text"
    with pytest.raises(Rejected) as info:
        box.extract("image/png", b"\x89PNG")
    assert info.value.reason == "unsupported_media_type"


def test_input_over_the_limit_is_refused_before_any_process_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a process must not be started")

    monkeypatch.setattr(subprocess, "Popen", boom)
    with pytest.raises(Rejected) as info:
        SandboxedExtractor(ExtractionLimits(max_input_bytes=10)).extract("text/plain", b"x" * 11)
    assert info.value.reason == "input_too_large"


# ------------------------------------------------------------------ resource controls


def test_a_child_that_never_answers_is_killed_at_the_timeout() -> None:
    started = time.monotonic()
    with pytest.raises(Rejected) as info:
        sandbox("sleeper", timeout_s=1.5).extract("text/plain", b"x")
    assert info.value.reason == "timeout"
    assert time.monotonic() - started < 15, "the child must be killed, not waited for"


def test_a_child_that_floods_stdout_is_killed_at_the_output_cap() -> None:
    started = time.monotonic()
    with pytest.raises(Rejected) as info:
        sandbox("flooder", timeout_s=20, max_text_chars=1000).extract("text/plain", b"x")
    assert info.value.reason == "output_too_large"
    assert time.monotonic() - started < 15


def test_a_child_that_dies_without_an_answer_is_a_rejection_not_a_hang() -> None:
    with pytest.raises(Rejected) as info:
        sandbox("crasher", timeout_s=10).extract("text/plain", b"x")
    assert info.value.reason == "extractor_crashed"


def test_failure_to_start_the_child_is_an_infrastructure_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise OSError("cannot fork")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    with pytest.raises(SandboxUnavailable):
        SandboxedExtractor(ExtractionLimits()).extract("text/plain", b"x")


# ------------------------------------------------------------------ what the child can see


def test_the_child_gets_no_secrets_and_a_scratch_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_WORKER_DATABASE_URL", "postgresql://rag_worker:hunter2@db/x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    result = sandbox("env_reporter", timeout_s=20).extract("text/plain", b"x")
    seen = json.loads(result.blocks[0].text)
    assert "hunter2" not in json.dumps(seen) and "sk-secret" not in json.dumps(seen)
    assert not [k for k in seen["env"] if k.startswith(("RAG_", "ANTHROPIC", "OPENAI", "XAI"))]
    allowed = {
        "PYTHONPATH",
        "PYTHONSAFEPATH",
        "PYTHONDONTWRITEBYTECODE",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
    }
    # Python itself may add locale variables on some platforms; nothing else is acceptable
    extra = set(seen["env"]) - allowed - {"LC_CTYPE", "LANG", "LC_ALL"}
    assert not extra, f"unexpected variables reached the child: {extra}"
    assert "rag-extract-" in seen["cwd"]
    assert Path(seen["cwd"]).resolve() != Path.cwd().resolve()
    assert not Path(seen["cwd"]).exists(), "the scratch directory is removed afterwards"


# ------------------------------------------------------------------ the answer is untrusted data


@pytest.mark.parametrize(
    ("lie", "reason"),
    [
        ("kind", "extractor_error"),  # a block kind we do not know
        ("level", "extractor_error"),  # heading level out of range
        ("page", "extractor_error"),  # page number 0
        ("shape", "extractor_error"),  # block with the wrong number of fields
        ("text", "extractor_error"),  # text that is not a string
        ("reason", "extractor_error"),  # a failure reason that is not a safe code
        ("notjson", "extractor_crashed"),
        ("list", "extractor_crashed"),  # JSON, but not an object
    ],
)
def test_an_invalid_answer_is_rejected_with_a_safe_code(lie: str, reason: str) -> None:
    with pytest.raises(Rejected) as info:
        sandbox("liar", timeout_s=20).extract(lie, b"x")
    assert info.value.reason == reason


def test_the_answer_is_bounded_by_the_text_limit_even_if_the_child_ignores_it() -> None:
    with pytest.raises(Rejected) as info:
        sandbox("liar", timeout_s=20, max_text_chars=1000).extract("toomuch", b"x")
    assert info.value.reason == "text_too_large"


def test_nul_and_direction_override_characters_are_removed_again_by_the_parent() -> None:
    result = sandbox("liar", timeout_s=20).extract("nul", b"x")
    assert [b.text for b in result.blocks] == ["abc"]


@pytest.mark.skipif(os.name == "nt", reason="RLIMIT_* exist on POSIX only")
def test_posix_memory_limit_turns_runaway_allocation_into_a_rejection() -> None:
    with pytest.raises(Rejected) as info:
        sandbox("hog", timeout_s=30, memory_bytes=256 * 1024 * 1024).extract("text/plain", b"x")
    assert info.value.reason in {"resource_limit", "extractor_crashed"}
