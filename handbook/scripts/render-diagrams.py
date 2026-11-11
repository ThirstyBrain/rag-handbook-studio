"""Render every Mermaid source in docs/assets/diagrams to SVG and PNG.

Output: docs/assets/images/diagrams/<name>.svg|png (generated; the .mmd file is the source of truth).
Used by the PDF build and by chapters that embed a static image next to the live Mermaid block.
Skips a diagram when its outputs are newer than the source (pass --force to re-render).
Exit code 1 if any diagram fails to render.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "assets" / "diagrams"
OUT = ROOT / "docs" / "assets" / "images" / "diagrams"
MMDC = ROOT / "scripts" / "tools" / "node_modules" / ".bin" / ("mmdc.cmd" if sys.platform == "win32" else "mmdc")
TIMEOUT_S = 120


def render(src: Path, out: Path) -> str | None:
    """Return an error message, or None on success."""
    args = [str(MMDC), "-i", str(src), "-o", str(out), "--quiet", "-b", "white"]
    if out.suffix == ".png":
        args += ["-s", "2"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"timeout after {TIMEOUT_S}s"
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout).strip()[:300]
    return None


def main() -> int:
    force = "--force" in sys.argv
    if not MMDC.exists():
        print(f"mermaid-cli not installed at {MMDC}. Run: cd scripts/tools && npm install", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    rendered = skipped = 0
    for src in sorted(SRC.glob("*.mmd")):
        for ext in (".svg", ".png"):
            out = OUT / f"{src.stem}{ext}"
            if not force and out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
                skipped += 1
                continue
            err = render(src, out)
            if err:
                failures.append(f"{src.name}{ext}: {err.splitlines()[0]}")
                if "chrome-headless-shell" in err:  # environment problem, not a diagram problem
                    print("FAIL environment:", err.splitlines()[0], file=sys.stderr)
                    return 2
            else:
                rendered += 1
    print(f"rendered={rendered} skipped={skipped} failed={len(failures)}")
    for f in failures:
        print("FAIL", f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
