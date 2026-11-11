"""Chapter 4 exercise: bad vs. improved chunking (stdlib only).

Sizes are measured in WORDS as a stand-in for tokens so the script has no
dependencies. Real systems must count tokens with the embedding model's
tokenizer (Chapter 2). Word counts are a teaching proxy, not a recommendation.

Demonstrates and asserts
  1. Naive fixed-size splitting cuts a sentence and detaches a table row from
     its header (bad chunking).
  2. Heading-aware splitting keeps sections together and attaches the heading
     path as metadata; an oversized section is split on paragraph boundaries.
  3. Table-aware handling repeats the header row in every table chunk.
  4. Overlap is applied only to splits within a section and never exceeds the
     limit; chunk IDs are deterministic (same input -> same IDs).
  5. Coverage: all original content appears in at least one chunk.

Run:  python -I ch04_chunking_demo.py
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

DOC = """# Leave Policy

## Parental leave

Employees are entitled to 16 weeks of paid parental leave. The leave may be taken
in one block or split into two blocks within 12 months of the birth or adoption.
Contractors are not covered by this policy unless their contract states otherwise.

## Leave allowances by country

| Country | Weeks | Paid |
|---------|-------|------|
| Germany | 14 | Yes |
| India | 26 | Yes |
| USA | 12 | No |
| France | 16 | Yes |
"""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    heading_path: str
    text: str


def words(s: str) -> int:
    return len(s.split())


def cid(doc_id: str, idx: int, text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{doc_id}:{idx}:{h}"


# ---- BAD: fixed-size on raw text ---------------------------------------------
def naive_fixed(text: str, size: int) -> list[str]:
    w = text.split()
    return [" ".join(w[i : i + size]) for i in range(0, len(w), size)]


# ---- GOOD: structure-aware ----------------------------------------------------
def sections(md: str) -> list[tuple[str, str]]:
    """Split Markdown into (heading_path, body). Headings kept in the path, not the body."""
    path: list[str] = []
    out: list[tuple[str, list[str]]] = []
    cur: list[str] = []
    cur_path = ""
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if cur and "".join(cur).strip():
                out.append((cur_path, cur))
            level, title = len(m.group(1)), m.group(2).strip()
            path = path[: level - 1] + [title]
            cur_path, cur = " > ".join(path), []
        else:
            cur.append(line)
    if cur and "".join(cur).strip():
        out.append((cur_path, cur))
    return [(p, "\n".join(b).strip()) for p, b in out]


def split_table(body: str, max_words: int) -> list[str]:
    """Split a Markdown table by rows, repeating header + separator in every chunk."""
    lines = [ln for ln in body.splitlines() if ln.strip()]
    header, rows = lines[:2], lines[2:]
    chunks, cur = [], []
    for row in rows:
        if cur and words("\n".join(header + cur + [row])) > max_words:
            chunks.append("\n".join(header + cur))
            cur = []
        cur.append(row)
    if cur:
        chunks.append("\n".join(header + cur))
    return chunks


def split_paragraphs(body: str, max_words: int, overlap_words: int) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    for p in paras:
        if cur and words(" ".join(cur + [p])) > max_words:
            chunks.append(" ".join(cur))
            tail = " ".join(" ".join(cur).split()[-overlap_words:]) if overlap_words else ""
            cur = ([tail] if tail else [])
        cur.append(p)
    if cur:
        chunks.append(" ".join(cur))
    # hard-wrap any single paragraph still above the limit (last resort)
    final: list[str] = []
    for c in chunks:
        w = c.split()
        if len(w) <= max_words:
            final.append(c)
        else:
            step = max(1, max_words - overlap_words)
            final.extend(" ".join(w[i : i + max_words]) for i in range(0, len(w), step))
    return final


def structure_aware(doc_id: str, md: str, max_words: int, overlap_words: int = 0) -> list[Chunk]:
    out: list[Chunk] = []
    for path, body in sections(md):
        is_table = body.lstrip().startswith("|")
        pieces = split_table(body, max_words) if is_table else split_paragraphs(body, max_words, overlap_words)
        for piece in pieces:
            out.append(Chunk(cid(doc_id, len(out), piece), path, piece))
    return out


def main() -> None:
    # 1) BAD chunking
    bad = naive_fixed(DOC, 30)
    joined_bad = "\n--\n".join(bad)
    print("== Naive fixed-size (30 words) ==")
    for i, c in enumerate(bad):
        print(f"[{i}] {c[:90]!r}...")
    # the table header row and body rows land in different chunks, and chunks have no heading context
    header_chunk = next(i for i, c in enumerate(bad) if "Country" in c)
    germany_chunk = next(i for i, c in enumerate(bad) if "Germany" in c)
    france_chunk = next(i for i, c in enumerate(bad) if "France" in c)
    assert not all("Country |" in bad[i] for i in {germany_chunk, france_chunk}), \
        "expected at least one table-row chunk without its header"
    assert all("Leave allowances" not in c for c in bad[france_chunk:]), "no heading context in later chunks"
    _ = (joined_bad, header_chunk)

    # 2-4) GOOD chunking
    good = structure_aware("leave-policy", DOC, max_words=45, overlap_words=10)
    print("\n== Structure-aware (max 45 words) ==")
    for c in good:
        print(f"{c.chunk_id}  [{c.heading_path}]  {c.text[:70]!r}...")

    assert all(words(c.text) <= 45 for c in good if not c.text.startswith("|")), "text chunk exceeds limit"
    assert all(c.heading_path for c in good), "every chunk carries a heading path"
    table_chunks = [c for c in good if c.text.startswith("|")]
    assert table_chunks and all("| Country | Weeks | Paid |" in c.text for c in table_chunks), \
        "header row must be repeated in every table chunk"
    assert any(c.heading_path == "Leave Policy > Parental leave" for c in good)

    # determinism
    again = structure_aware("leave-policy", DOC, max_words=45, overlap_words=10)
    assert [c.chunk_id for c in good] == [c.chunk_id for c in again], "chunk IDs must be deterministic"

    # tighter limit forces a table split: header repeated, no row lost
    tiny = structure_aware("leave-policy", DOC, max_words=16, overlap_words=0)
    tbl = [c for c in tiny if c.text.startswith("|")]
    assert len(tbl) >= 2, "table should split under a tight limit"
    rows = {r for c in tbl for r in c.text.splitlines()[2:]}
    assert rows == {"| Germany | 14 | Yes |", "| India | 26 | Yes |", "| USA | 12 | No |", "| France | 16 | Yes |"}

    # 5) coverage: every original sentence fragment survives somewhere
    corpus = " ".join(c.text for c in good)
    for needle in ("16 weeks of paid parental leave", "Contractors are not covered", "| USA | 12 | No |"):
        assert needle in corpus, needle

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
