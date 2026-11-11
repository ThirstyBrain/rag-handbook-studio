"""Validate Mermaid diagrams (CLAUDE.md 8.2: diagrams must render).

Checks
  1. Every docs/assets/diagrams/*.mmd renders with mermaid-cli.
  2. Every ```mermaid block in docs/chapters/*.md renders.
  3. Every chapter block is identical to a .mmd source (no drift between
     the chapter and docs/assets/diagrams/).

Setup (once):  cd scripts/tools && npm install
Usage:         python -I scripts/validate-diagrams.py
Exit code 0 only if all checks pass.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "docs" / "assets" / "diagrams"
CHAPTERS = ROOT / "docs" / "chapters"
MMDC = ROOT / "scripts" / "tools" / "node_modules" / ".bin" / ("mmdc.cmd" if sys.platform == "win32" else "mmdc")
BLOCK = re.compile(r"```mermaid\r?\n(.*?)```", re.S)


def norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def render(src: Path, out_dir: Path) -> tuple[bool, str]:
    out = out_dir / (src.stem + ".svg")
    proc = subprocess.run(
        [str(MMDC), "-i", str(src), "-o", str(out), "--quiet"],
        capture_output=True, text=True, timeout=180,
    )
    ok = proc.returncode == 0 and out.exists()
    return ok, (proc.stderr or proc.stdout).strip()


def main() -> int:
    if not MMDC.exists():
        print(f"mermaid-cli not installed at {MMDC}. Run: cd scripts/tools && npm install", file=sys.stderr)
        return 2

    failures = 0
    sources = {norm(p.read_text(encoding="utf-8")): p for p in sorted(DIAGRAMS.glob("*.mmd"))}

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        print(f"== Rendering {len(sources)} diagram source files ==")
        for p in sorted(DIAGRAMS.glob("*.mmd")):
            ok, msg = render(p, tmpdir)
            print(f"{'OK  ' if ok else 'FAIL'} {p.relative_to(ROOT)}" + ("" if ok else f"\n     {msg}"))
            failures += not ok

        print("\n== Chapter blocks ==")
        for ch in sorted(CHAPTERS.glob("[0-9][0-9]-*.md")):
            blocks = BLOCK.findall(ch.read_text(encoding="utf-8"))
            for i, body in enumerate(blocks, 1):
                tmp_src = tmpdir / f"{ch.stem}-block{i}.mmd"
                tmp_src.write_text(body, encoding="utf-8")
                ok, msg = render(tmp_src, tmpdir)
                match = sources.get(norm(body))
                label = f"{ch.name} block {i}"
                if not ok:
                    print(f"FAIL {label}: does not render\n     {msg}")
                    failures += 1
                elif match is None:
                    print(f"FAIL {label}: renders but matches no docs/assets/diagrams/*.mmd source")
                    failures += 1
                else:
                    print(f"OK   {label} == {match.name}")

    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} problem(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
