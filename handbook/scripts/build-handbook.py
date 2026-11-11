"""Build docs/RAG-Architecture-Handbook.md deterministically from docs/chapters/*.md.

Usage:  python -I scripts/build-handbook.py

- Chapters are concatenated in filename order (NN-slug.md).
- The output is fully regenerated; never edit it by hand (CLAUDE.md 5.2).
- Prints chapter count and a content hash so drift is detectable.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "docs" / "chapters"
OUT = ROOT / "docs" / "RAG-Architecture-Handbook.md"

HEADER = """# The Production-Grade RAG Architecture & Engineering Handbook

*From Fundamentals to Enterprise-Scale Intelligent Retrieval Systems*

> GENERATED FILE. Source of truth: `docs/chapters/*.md`. Rebuild with `python -I scripts/build-handbook.py`.
> Completion status per chapter: `project-management/MASTER-TOC.md`.

"""


def main() -> int:
    files = sorted(p for p in CHAPTERS.glob("[0-9][0-9]-*.md"))
    if not files:
        print("No chapter files found.", file=sys.stderr)
        return 1
    parts = [HEADER]
    for f in files:
        text = f.read_text(encoding="utf-8").rstrip() + "\n"
        text = text.replace("](../assets/", "](assets/")  # chapters live one level below docs/
        parts.append(f"\n---\n\n<!-- source: docs/chapters/{f.name} -->\n\n{text}")
    content = "".join(parts)
    OUT.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    print(f"Built {OUT.relative_to(ROOT)}: {len(files)} chapters, {len(content):,} chars, sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
