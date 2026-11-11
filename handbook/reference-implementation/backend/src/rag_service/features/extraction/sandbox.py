"""Run extraction in a separate, resource-limited process (ADR-016).

Why a process: parsers for PDF and Office formats are large, complex and historically a source of memory
and CPU exhaustion and memory-safety bugs. In the worker process such a failure would take down the
worker, which holds database credentials. The child holds none: it gets an empty environment, a scratch
working directory and no stderr, and its answer is validated here as untrusted data.

Controls and their limits (stated, not implied):
  * wall-clock timeout, enforced here on every platform (the child is killed);
  * output size cap, enforced here while reading (the child is killed when it is exceeded);
  * address-space, CPU and file-size rlimits, applied by the child on POSIX only. On Windows only the
    timeout and output cap apply: the deployed image is Linux, and a Windows host is a development host;
  * NOT provided: network isolation, a filesystem jail or syscall filtering. A compromised parser could
    still read what its OS user can read. Container-level controls (read-only root, no network policy,
    non-root user) are the layer for that, see the infrastructure component.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from rag_service.features.extraction.model import (
    BLOCK_KINDS,
    Block,
    Extracted,
    ExtractionLimits,
    Rejected,
    clean_text,
)

_CHILD_MODULE = "rag_service.features.extraction.child"
_SRC_ROOT = str(Path(__file__).resolve().parents[3])
_CHUNK = 65536
_REASON_CODE = frozenset("abcdefghijklmnopqrstuvwxyz_")


class SandboxUnavailable(Exception):
    """The child process could not be started: an infrastructure fault, so retrying may help."""


class SandboxedExtractor:
    def __init__(
        self,
        limits: ExtractionLimits,
        *,
        child_module: str = _CHILD_MODULE,
        extra_python_paths: tuple[str, ...] = (),
    ) -> None:
        """``child_module`` and ``extra_python_paths`` exist so tests can run misbehaving children."""
        self._limits = limits
        self._module = child_module
        self._paths = os.pathsep.join((_SRC_ROOT, *extra_python_paths))

    def extract(self, media_type: str, data: bytes) -> Extracted:
        limits = self._limits
        if len(data) > limits.max_input_bytes:
            raise Rejected("input_too_large")
        # JSON escapes can expand text up to 6x; allow for that plus structure
        output_cap = limits.max_text_chars * 6 + 1024 * 1024
        header = json.dumps({"media_type": media_type, "limits": json.loads(limits.to_json())})
        env = {"PYTHONPATH": self._paths, "PYTHONSAFEPATH": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":  # Windows needs these to start a Python process; neither is a secret
            env.update({k: os.environ[k] for k in ("SYSTEMROOT", "SYSTEMDRIVE") if k in os.environ})
        out = bytearray()
        overflow = threading.Event()
        with tempfile.TemporaryDirectory(prefix="rag-extract-") as scratch:
            try:
                proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
                    [sys.executable, "-B", "-m", self._module],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    cwd=scratch,
                )
            except OSError:
                raise SandboxUnavailable from None
            assert proc.stdin is not None and proc.stdout is not None

            def feed() -> None:
                try:
                    proc.stdin.write(header.encode() + b"\n" + data)  # type: ignore[union-attr]
                    proc.stdin.close()  # type: ignore[union-attr]
                except OSError:
                    pass  # the child exited early; its result (or crash) is handled below

            def drain() -> None:
                while chunk := proc.stdout.read(_CHUNK):  # type: ignore[union-attr]
                    out.extend(chunk)
                    if len(out) > output_cap:
                        overflow.set()
                        proc.kill()
                        return

            threads = [
                threading.Thread(target=feed, daemon=True),
                threading.Thread(target=drain, daemon=True),
            ]
            for t in threads:
                t.start()
            try:
                proc.wait(timeout=limits.timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise Rejected("timeout") from None
            finally:
                for t in threads:
                    t.join(timeout=5)
        if overflow.is_set():
            raise Rejected("output_too_large")
        return _parse(bytes(out), limits)


def _parse(raw: bytes, limits: ExtractionLimits) -> Extracted:
    """Validate the child's answer: it is untrusted data, however it was produced."""
    try:
        message = json.loads(raw)
    except ValueError:
        raise Rejected(
            "extractor_crashed"
        ) from None  # killed, out of memory, or exited without an answer
    if not isinstance(message, dict):
        raise Rejected("extractor_crashed")
    if message.get("ok") is not True:
        reason = message.get("reason")
        ok = isinstance(reason, str) and 0 < len(reason) <= 64 and set(reason) <= _REASON_CODE
        raise Rejected(reason if ok else "extractor_error")  # type: ignore[arg-type]
    extractor, raw_blocks = message.get("extractor"), message.get("blocks")
    if not isinstance(extractor, str) or not isinstance(raw_blocks, list) or len(extractor) > 100:
        raise Rejected("extractor_error")
    blocks: list[Block] = []
    total = 0
    for item in raw_blocks:
        if not (isinstance(item, list) and len(item) == 4):
            raise Rejected("extractor_error")
        kind, text, level, page = item
        if (
            kind not in BLOCK_KINDS
            or not isinstance(text, str)
            or not isinstance(level, int)
            or isinstance(level, bool)
            or not 0 <= level <= 6
            or not (
                page is None or (isinstance(page, int) and not isinstance(page, bool) and page >= 1)
            )
        ):
            raise Rejected("extractor_error")
        text = clean_text(
            text
        )  # again here: a misbehaving child must not be able to deliver NUL bytes
        total += len(text)
        if total > limits.max_text_chars:
            raise Rejected("text_too_large")
        if text.strip():
            blocks.append(Block(kind, text, level, page))
    if not blocks:
        raise Rejected("no_text")
    return Extracted(extractor, tuple(blocks))
