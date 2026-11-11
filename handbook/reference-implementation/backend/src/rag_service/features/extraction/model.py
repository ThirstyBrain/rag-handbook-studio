"""Extraction data model, limits and text hygiene. Imported by both the worker and the sandboxed child, so
it depends on the standard library only."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

BLOCK_KINDS = frozenset({"heading", "paragraph", "list_item", "code", "table"})


class Rejected(Exception):
    """The file cannot be processed and retrying will not help. ``reason`` is a short safe code
    (letters and underscores), never file content: it is stored and logged."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Block:
    """One structural unit of a document. For ``table`` the text is one row per line, the first line
    being the header row. ``level`` is the heading level (1-6), else 0. ``page`` is 1-based or None."""

    kind: str
    text: str
    level: int = 0
    page: int | None = None


@dataclass(frozen=True)
class Extracted:
    extractor: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class ExtractionLimits:
    timeout_s: float = 30.0
    memory_bytes: int = 1024 * 1024 * 1024
    max_input_bytes: int = 25 * 1024 * 1024
    max_pages: int = 1000
    max_text_chars: int = 5_000_000
    max_zip_members: int = 2000
    max_uncompressed_bytes: int = 100 * 1024 * 1024
    max_compression_ratio: float = 100.0
    max_xml_depth: int = 200

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> ExtractionLimits:
        return cls(**json.loads(raw))


# C0/C1 controls except tab and newline; DEL; bidirectional overrides and isolates (text-spoofing);
# BOM / zero-width no-break space; the Unicode "tag" block (invisible-text smuggling).
_STRIP = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069\ufeff\U000e0000-\U000e007f]"
)
_SURROGATES = re.compile(r"[\ud800-\udfff]")


def clean_text(text: str) -> str:
    """Make extracted text safe to store: PostgreSQL text cannot hold NUL, lone surrogates are not valid
    UTF-8, and invisible or direction-overriding characters let a document hide or disguise content.
    This is hygiene, not an injection defence: visible hostile instructions are kept as data."""
    text = _SURROGATES.sub("\ufffd", text)  # lone surrogates cannot be encoded as UTF-8
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", _STRIP.sub("", text))
