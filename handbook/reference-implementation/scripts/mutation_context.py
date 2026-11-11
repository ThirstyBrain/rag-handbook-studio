"""Mutation check for context assembly (component 10). Same method as mutation_extract.py; no database needed.
Run from reference-implementation/backend:  python ../scripts/mutation_context.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_extract as mx

C = mx.FEATURES / "generation" / "context.py"
UNIT = ["../tests/unit/test_context.py"]

MUTANTS: list[mx.Mutant] = [
    (C, "(len(text) + 3) // 4", "len(text) // 4", "token estimate rounds down", UNIT),
    (C, "if fp in seen:", "if False:", "duplicates kept", UNIT),
    (C, "_WS.sub(\" \", text).strip().casefold()", "text", "no normalisation before dedup", UNIT),
    (C, "if not fp:", "if False:", "empty passages kept", UNIT),
    (C, "if len(chosen) >= cfg.max_passages:", "if False:", "passage count unbounded", UNIT),
    (C, "if per_doc.get(c.document_id, 0) >= cfg.max_per_document:", "if False:", "document cap ignored", UNIT),
    (C, "if used + tokens > cfg.max_context_tokens:", "if used + tokens >= cfg.max_context_tokens:", "budget off by one", UNIT),
    (C, "if used + tokens > cfg.max_context_tokens:", "if False:", "budget ignored", UNIT),
    (C, "dropped[\"over_budget\"] += 1  # skip it, a smaller later passage may still fit\n            continue", "dropped[\"over_budget\"] += 1\n            break", "stops at first oversize passage", UNIT),
    (C, "source_id=f\"S{len(chosen) + 1}\"", "source_id=f\"S{len(chosen)}\"", "source ids start at 0", UNIT),
    (C, "{neutralise(passage.text)}", "{passage.text}", "passage text not neutralised", UNIT),
    (C, "neutralise(passage.section_path).replace(chr(34), chr(39))", "passage.section_path", "section not neutralised", UNIT),
    (C, r"<\s*/?\s*(?:source", "</?(?:source", "spaced tags not neutralised", UNIT),
    (C, "else f\"{passage.page_start}-{passage.page_end}\"", "else f\"{passage.page_start}\"", "page range lost", UNIT),
    (C, "if not 1 <= self.max_per_document <= self.max_passages:", "if False:", "per-document cap not validated", UNIT),
    (C, "if self.max_context_tokens < 1 or", "if", "token budget not validated", UNIT),
]

if __name__ == "__main__":
    mx.UNIT, mx.DB, mx.MUTANTS = UNIT, [], MUTANTS
    raise SystemExit(mx.main())
