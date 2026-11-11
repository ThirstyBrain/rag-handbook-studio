"""Choose the parser by media type and enforce the output limits. Runs inside the sandboxed child."""

from __future__ import annotations

from rag_service.features.extraction.docx import docx_blocks
from rag_service.features.extraction.model import (
    Block,
    Extracted,
    ExtractionLimits,
    Rejected,
    clean_text,
)
from rag_service.features.extraction.pdf import pdf_blocks, pdf_version
from rag_service.features.extraction.textual import html_blocks, markdown_blocks, plain_text_blocks

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TEXT_PARSERS = {
    "text/plain": ("text-1", plain_text_blocks),
    "text/markdown": ("markdown-1", markdown_blocks),
    "text/html": ("html-stdlib-1", html_blocks),
}


def extract(media_type: str, data: bytes, limits: ExtractionLimits) -> Extracted:
    if len(data) > limits.max_input_bytes:
        raise Rejected("input_too_large")
    if media_type == PDF:
        extractor, blocks = f"pypdf-{pdf_version()}", pdf_blocks(data, limits)
    elif media_type == DOCX:
        extractor, blocks = "docx-stdlib-1", docx_blocks(data, limits)
    elif media_type in _TEXT_PARSERS:
        extractor, parser = _TEXT_PARSERS[media_type]
        try:
            blocks = parser(clean_text(data.decode("utf-8", errors="replace")))
        except RecursionError:
            raise Rejected("too_deep") from None
    else:
        raise Rejected("unsupported_media_type")
    return Extracted(extractor, _finish(blocks, limits))


def _finish(blocks: list[Block], limits: ExtractionLimits) -> tuple[Block, ...]:
    out: list[Block] = []
    total = 0
    for block in blocks:
        text = clean_text(block.text)
        text = text.strip(chr(10)) if block.kind == "code" else text.strip()
        if not text.strip():
            continue
        total += len(text)
        if total > limits.max_text_chars:
            raise Rejected("text_too_large")
        out.append(Block(block.kind, text, block.level, block.page))
    if not out:
        raise Rejected(
            "no_text"
        )  # for example a scanned PDF: there is nothing to index without OCR
    return tuple(out)
