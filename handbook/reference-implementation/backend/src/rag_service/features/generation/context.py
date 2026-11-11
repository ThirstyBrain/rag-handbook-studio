"""Context assembly: turn ranked hits into a bounded, de-duplicated, citable block of UNTRUSTED data.

Pure and deterministic (no I/O). Responsibilities, in order:
  1. drop exact and whitespace/case-normalised duplicate passages (re-chunked or repeated text);
  2. cap passages per document so one long document cannot crowd out the others (diversity);
  3. fit a token budget, never cutting a passage mid-way (a dropped passage is reported, not truncated);
  4. assign short opaque source ids (``S1``, ``S2`` ...) that the model cites and that citation validation
     (component 12) maps back to chunk ids server-side - the model never sees or invents real identifiers;
  5. render each passage inside an explicit delimiter, neutralising any delimiter text inside the content.

SECURITY: retrieved text is data, not instructions. Delimiting and neutralising reduce, but do NOT eliminate,
prompt-injection risk; the real controls are authorize-before-retrieve, no tools in the generation call, and
output validation (components 11-12, ADR-010). Token counting here is an ESTIMATE (chars / 4 by default,
deliberately conservative); swap in the provider tokenizer through ``count_tokens`` when exact budgets matter.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from rag_service.features.retrieval.fusion import FusedHit

_WS = re.compile(r"\s+")
# Anything that could close or forge a passage wrapper inside retrieved content.
_FORGED_TAG = re.compile(r"<\s*/?\s*(?:source|context|passage)\b[^>]*>", re.IGNORECASE)
TokenCounter = Callable[[str], int]


def estimate_tokens(text: str) -> int:
    """Conservative estimate: one token per 4 characters, rounded up, at least 1 for non-empty text."""
    return (len(text) + 3) // 4


@dataclass(frozen=True)
class AssemblyConfig:
    max_context_tokens: int = 3000
    max_passages: int = 12
    max_per_document: int = 3
    count_tokens: TokenCounter = estimate_tokens

    def __post_init__(self) -> None:
        if self.max_context_tokens < 1 or not 1 <= self.max_passages <= 100:
            raise ValueError("invalid context budget")
        if not 1 <= self.max_per_document <= self.max_passages:
            raise ValueError("max_per_document must be between 1 and max_passages")


@dataclass(frozen=True)
class Passage:
    source_id: str  # "S1".. what the model cites
    chunk_id: UUID
    document_id: UUID
    version: int
    ordinal: int
    text: str
    section_path: str | None
    page_start: int | None
    page_end: int | None
    tokens: int


@dataclass(frozen=True)
class AssembledContext:
    passages: list[Passage]
    rendered: str
    tokens: int
    dropped: dict[str, int] = field(default_factory=dict)  # reason -> count

    def by_source_id(self) -> dict[str, Passage]:
        return {p.source_id: p for p in self.passages}


def neutralise(text: str) -> str:
    """Defang wrapper-like tags in retrieved content so a passage cannot close its own delimiter."""
    return _FORGED_TAG.sub("[tag removed]", text)


def _fingerprint(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def _render(passage: Passage) -> str:
    where = []
    if passage.section_path:
        where.append(f'section="{neutralise(passage.section_path).replace(chr(34), chr(39))}"')
    if passage.page_start is not None:
        pages = (
            f"{passage.page_start}"
            if passage.page_end in (None, passage.page_start)
            else f"{passage.page_start}-{passage.page_end}"
        )
        where.append(f'pages="{pages}"')
    attrs = (" " + " ".join(where)) if where else ""
    return f'<source id="{passage.source_id}"{attrs}>\n{neutralise(passage.text)}\n</source>'


def assemble_context(
    hits: Sequence[FusedHit], config: AssemblyConfig | None = None
) -> AssembledContext:
    """Select and render passages from ``hits`` (best first). The input order is the priority order."""
    cfg = config or AssemblyConfig()
    dropped = {"duplicate": 0, "document_cap": 0, "over_budget": 0, "max_passages": 0, "empty": 0}
    seen: set[str] = set()
    per_doc: dict[UUID, int] = {}
    chosen: list[Passage] = []
    used = 0
    for hit in hits:
        c = hit.candidate
        fp = _fingerprint(c.content)
        if not fp:
            dropped["empty"] += 1
            continue
        if fp in seen:
            dropped["duplicate"] += 1
            continue
        if len(chosen) >= cfg.max_passages:
            dropped["max_passages"] += 1
            continue
        if per_doc.get(c.document_id, 0) >= cfg.max_per_document:
            dropped["document_cap"] += 1
            continue
        tokens = cfg.count_tokens(c.content)
        if used + tokens > cfg.max_context_tokens:
            dropped["over_budget"] += 1  # skip it, a smaller later passage may still fit
            continue
        seen.add(fp)
        per_doc[c.document_id] = per_doc.get(c.document_id, 0) + 1
        used += tokens
        chosen.append(
            Passage(
                source_id=f"S{len(chosen) + 1}",
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                version=c.version,
                ordinal=c.ordinal,
                text=c.content,
                section_path=c.section_path,
                page_start=c.page_start,
                page_end=c.page_end,
                tokens=tokens,
            )
        )
    rendered = "\n\n".join(_render(p) for p in chosen)
    return AssembledContext(
        passages=chosen,
        rendered=rendered,
        tokens=used,
        dropped={k: v for k, v in dropped.items() if v},
    )
