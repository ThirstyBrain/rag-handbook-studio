"""Structure-aware chunking (ADR-003, ADR-016). Pure, deterministic, no I/O.

Rules, each checked by a test:
  * a chunk never spans two sections: a heading always starts a new chunk and overlap never crosses it;
  * every chunk carries its section path ("Policy > Leave > Parental"), so a chunk is attributable;
  * sentences, code lines and table rows are the smallest units; a unit larger than the target is split
    at whitespace, then by characters, so no chunk exceeds ``target_tokens`` (a test asserts it);
  * a table that continues into a later chunk repeats its header row first;
  * overlap is whole trailing units of the previous chunk of the SAME section, at most ``overlap_tokens``;
  * the same input and configuration always give the same chunks.

Token counts are an ESTIMATE (characters / chars_per_token), not a model tokenizer. ADR-003 asks for the
embedding model's own tokenizer; this is replaced behind ``TokenCounter`` when the embedding model is
fixed (component 5). The estimate is conservative for English prose and unreliable for other scripts.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from rag_service.features.extraction.model import Block, Rejected

CHUNKER_VERSION = "structure-v1"
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_PATH_PART_MAX = 200

TokenCounter = Callable[[str], int]


@dataclass(frozen=True)
class ChunkConfig:
    target_tokens: int = 512
    max_tokens: int = 768
    overlap_tokens: int = 50
    chars_per_token: float = 4.0
    max_chunks: int = 20_000

    def __post_init__(self) -> None:
        if not 0 <= self.overlap_tokens < self.target_tokens <= self.max_tokens:
            raise ValueError("need 0 <= overlap_tokens < target_tokens <= max_tokens")
        if self.chars_per_token <= 0 or self.max_chunks < 1:
            raise ValueError("chars_per_token and max_chunks must be positive")

    def count(self, text: str) -> int:
        return math.ceil(len(text) / self.chars_per_token) if text else 0


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    content: str
    section_path: str
    token_count: int
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class _Unit:
    text: str
    tokens: int
    page: int | None
    sep: str  # what joins this unit to the previous one inside a chunk
    header: str | None = None  # the table header row, for table rows
    is_header: bool = False


def chunk_blocks(blocks: tuple[Block, ...] | list[Block], config: ChunkConfig) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    section: list[_Unit] = []

    def flush() -> None:
        path = " > ".join(text for _, text in stack)
        chunks.extend(_pack(section, path, config, len(chunks)))
        if len(chunks) > config.max_chunks:
            raise Rejected("too_many_chunks")
        section.clear()

    for block in blocks:
        if block.kind == "heading":
            flush()
            level = max(1, block.level)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, block.text[:_PATH_PART_MAX]))
        else:
            section.extend(_units(block, config))
    flush()
    return chunks


def _units(block: Block, config: ChunkConfig) -> list[_Unit]:
    cap = max(1, int(config.target_tokens * config.chars_per_token))
    page = block.page
    out: list[_Unit] = []
    if block.kind == "table":
        rows = [r for r in block.text.split("\n") if r.strip()]
        header = rows[0] if rows else None
        # a repeated header must fit in the headroom between the target and the hard maximum
        room = min(config.target_tokens // 4, config.max_tokens - config.target_tokens)
        header_ok = header is not None and config.count(header + "\n") <= room
        for i, row in enumerate(rows):
            for j, piece in enumerate(_split(row, cap)):
                out.append(
                    _Unit(piece, config.count(piece), page, "\n",
                          header if header_ok else None, is_header=(i == 0 and j == 0))
                )  # fmt: skip
        return out
    if block.kind == "code":
        for line in block.text.split("\n"):
            out.extend(
                _Unit(p, config.count(p), page, "\n") for p in _split(line, cap) if p.strip()
            )
        return out
    first = True
    for sentence in _SENTENCE.split(block.text):
        for piece in _split(sentence.strip(), cap):
            out.append(_Unit(piece, config.count(piece), page, "\n\n" if first else " "))
            first = False
    if block.kind == "list_item" and out:
        out[0] = _Unit(out[0].text, out[0].tokens, page, "\n")
    return out


def _split(text: str, cap: int) -> list[str]:
    """Split ``text`` into pieces of at most ``cap`` characters, at whitespace where possible."""
    if len(text) <= cap:
        return [text] if text else []
    pieces: list[str] = []
    rest = text
    while len(rest) > cap:
        cut = rest.rfind(" ", 0, cap + 1)
        if cut <= 0:
            cut = cap
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()
    if rest:
        pieces.append(rest)
    return [p for p in pieces if p]


def _text(units: list[_Unit]) -> str:
    first = units[0]
    body = first.text + "".join(u.sep + u.text for u in units[1:])
    if first.header is not None and not first.is_header:
        return first.header + "\n" + body
    return body


def _pack(units: list[_Unit], path: str, config: ChunkConfig, start: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[_Unit] = []
    new_units = 0

    def tokens(items: list[_Unit]) -> int:
        # the size of the text a chunk would really contain (separators and repeated header included),
        # not a sum of unit sizes, so the target holds exactly
        return config.count(_text(items)) if items else 0

    def emit() -> None:
        pages = [u.page for u in current if u.page is not None]
        text = _text(current)
        chunks.append(
            Chunk(start + len(chunks), text, path, config.count(text),
                  min(pages) if pages else None, max(pages) if pages else None)
        )  # fmt: skip

    def carry() -> list[_Unit]:
        kept: list[_Unit] = []
        total = 0
        for unit in reversed(current):
            if total + unit.tokens > config.overlap_tokens:
                break
            kept.insert(0, unit)
            total += unit.tokens
        return kept

    for unit in units:
        if new_units and tokens([*current, unit]) > config.target_tokens:
            emit()
            current = carry()
            new_units = 0
            while current and tokens([*current, unit]) > config.target_tokens:
                current.pop(0)  # the overlap is optional, the size cap is not
        current.append(unit)
        new_units += 1
    if new_units:
        emit()
    return chunks
