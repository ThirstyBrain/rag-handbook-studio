"""PDF to blocks with pypdf (BSD-3-Clause, pure Python, ADR-016).

PDFs carry no semantic structure, so every block is a paragraph with its page number; headings and tables
are not recovered (a layout service is the documented upgrade path, ADR-003). Scanned pages yield no text
and no OCR is attempted. Encrypted files are rejected rather than opened with guessed passwords.
pypdf's maintainers state that callers must catch its exceptions; every failure here is a ``Rejected``.
"""

from __future__ import annotations

import io
import re

from rag_service.features.extraction.model import Block, ExtractionLimits, Rejected

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def pdf_blocks(data: bytes, limits: ExtractionLimits) -> list[Block]:
    from pypdf import PdfReader  # imported here: only the PDF path pays for it

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise Rejected("encrypted_pdf")
        page_count = len(reader.pages)
        if page_count > limits.max_pages:
            raise Rejected("too_many_pages")
        blocks: list[Block] = []
        total = 0
        for number in range(page_count):
            text = reader.pages[number].extract_text() or ""
            total += len(text)
            if total > limits.max_text_chars:
                raise Rejected("text_too_large")
            for paragraph in _PARAGRAPH_BREAK.split(text):
                flat = " ".join(paragraph.split())
                if flat:
                    blocks.append(Block("paragraph", flat, page=number + 1))
        return blocks
    except Rejected:
        raise
    except MemoryError:
        raise Rejected("resource_limit") from None
    except Exception:
        raise Rejected("malformed_pdf") from None


def pdf_version() -> str:
    import pypdf

    return str(pypdf.__version__)
