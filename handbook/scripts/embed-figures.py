"""Embed the rendered diagram image above each Mermaid block in docs/chapters/*.md.

Each ```mermaid block that matches a docs/assets/diagrams/*.mmd source becomes:

    <!-- figure:NAME -->
    ![Figure C.K: <nearest heading>](../assets/images/diagrams/NAME.svg)
    *Figure C.K: <nearest heading>. Original diagram (source below).*
    <details><summary>Mermaid source</summary> ...block... </details>
    <!-- /figure -->

The image renders in any Markdown viewer and in the PDF; the Mermaid source stays in the file so
validate-diagrams.py keeps checking it. Idempotent: already-wrapped blocks are left alone.
Run scripts/render-diagrams.py first. Use --check to report without writing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "docs" / "assets" / "diagrams"
IMAGES = ROOT / "docs" / "assets" / "images" / "diagrams"
CHAPTERS = ROOT / "docs" / "chapters"
FENCE = re.compile(r"```mermaid\r?\n(.*?)```", re.S)
HEADING = re.compile(r"^#{2,4}\s+(?:\d+(?:\.\d+)*\.?\s+)?(.+?)\s*$")


def norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def nearest_heading(text: str, pos: int) -> str:
    for line in reversed(text[:pos].splitlines()):
        m = HEADING.match(line)
        if m:
            return m.group(1).replace("*", "").replace("`", "")
    return "Diagram"


def main() -> int:
    check = "--check" in sys.argv
    sources = {norm(p.read_text(encoding="utf-8")): p.stem for p in DIAGRAMS.glob("*.mmd")}
    unmatched: list[str] = []
    changed = 0
    for ch in sorted(CHAPTERS.glob("[0-9][0-9]-*.md")):
        text = ch.read_text(encoding="utf-8")
        chapter_no = int(ch.name[:2])
        out: list[str] = []
        last = 0
        k = 0
        for m in FENCE.finditer(text):
            k += 1
            if text[:m.start()].rstrip().endswith("<summary>Mermaid source</summary>"):
                continue  # already wrapped
            name = sources.get(norm(m.group(1)))
            if name is None or not (IMAGES / f"{name}.svg").exists():
                unmatched.append(f"{ch.name} block {k}")
                continue
            title = nearest_heading(text, m.start())
            label = f"Figure {chapter_no}.{k}: {title}"
            out.append(text[last:m.start()])
            out.append(
                f"<!-- figure:{name} -->\n"
                f"![{label}](../assets/images/diagrams/{name}.svg)\n\n"
                f"*{label}. Original diagram; source below.*\n\n"
                f"<details><summary>Mermaid source</summary>\n\n"
                f"{m.group(0)}\n\n</details>\n<!-- /figure -->"
            )
            last = m.end()
        out.append(text[last:])
        new = "".join(out)
        if new != text:
            changed += 1
            if not check:
                ch.write_text(new, encoding="utf-8", newline="\n")
    print(f"chapters {'to change' if check else 'changed'}={changed} unmatched={len(unmatched)}")
    for u in unmatched:
        print("UNMATCHED", u)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
