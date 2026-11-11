"""Sandboxed extraction child. Reads one request from stdin, writes one JSON result to stdout.

    python -m rag_service.features.extraction.child

stdin : one header line (JSON: media_type and the limits), then the raw file bytes until EOF.
stdout: {"ok": true, "extractor": ..., "blocks": [[kind, text, level, page], ...]} or
        {"ok": false, "reason": "<safe code>"}.

The parent (sandbox.py) starts this process with an empty environment (no database URLs or keys), a
scratch working directory and a timeout. On POSIX the child also lowers its own address-space, CPU and
file-size limits before it touches the file. It never writes anything but the result to stdout and
never writes file-derived text to stderr.
"""

from __future__ import annotations

import json
import sys

from rag_service.features.extraction.model import ExtractionLimits, Rejected

_HEADER_MAX = 64 * 1024


def _apply_posix_limits(limits: ExtractionLimits) -> None:
    try:
        import resource  # POSIX only
    except ImportError:
        return
    cpu = int(limits.timeout_s) + 1
    for name, value in (
        ("RLIMIT_AS", limits.memory_bytes),
        ("RLIMIT_CPU", cpu),
        ("RLIMIT_FSIZE", 0),  # the child has no reason to create files
    ):
        which = getattr(resource, name, None)
        if which is not None:
            resource.setrlimit(which, (value, value))  # type: ignore[attr-defined,unused-ignore]


def _emit(payload: dict[str, object]) -> None:
    # ASCII-only JSON: independent of the child's stdout encoding on any platform
    sys.stdout.write(json.dumps(payload, separators=(",", ":")))
    sys.stdout.flush()


def main() -> int:
    header = sys.stdin.buffer.readline(_HEADER_MAX)
    try:
        request = json.loads(header)
        limits = ExtractionLimits.from_json(json.dumps(request["limits"]))
        media_type = str(request["media_type"])
    except (ValueError, KeyError, TypeError):
        _emit({"ok": False, "reason": "bad_request"})
        return 0
    _apply_posix_limits(limits)
    try:
        data = sys.stdin.buffer.read(limits.max_input_bytes + 1)
        from rag_service.features.extraction.dispatch import extract

        result = extract(media_type, data, limits)
    except Rejected as exc:
        _emit({"ok": False, "reason": exc.reason})
    except MemoryError:
        _emit({"ok": False, "reason": "resource_limit"})
    except Exception:
        _emit({"ok": False, "reason": "extractor_error"})
    else:
        _emit(
            {
                "ok": True,
                "extractor": result.extractor,
                "blocks": [[b.kind, b.text, b.level, b.page] for b in result.blocks],
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
