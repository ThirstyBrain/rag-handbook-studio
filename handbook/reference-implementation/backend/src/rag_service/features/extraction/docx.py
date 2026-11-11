"""Word (.docx) to blocks with the standard library: a zip container holding XML.

Hostile-file defences, each covered by a test:
  * member count, declared total size and compression ratio are checked before anything is read;
  * reads are capped by the bytes actually produced, so a header that lies about sizes does not help;
  * XML containing a DOCTYPE (hence entities) is refused, which closes entity-expansion attacks;
  * XML nesting depth is capped; parsing is streaming and elements are released as they are consumed;
  * text marked hidden (w:vanish) is skipped, deleted tracked-change text is not a w:t element.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

from rag_service.features.extraction.model import Block, ExtractionLimits, Rejected

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_STYLE_HEADING = re.compile(r"^(?:Heading|heading)\s*([1-9])$")
_DOCTYPE = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_MIB = 1024 * 1024


def _read_document_xml(data: bytes, limits: ExtractionLimits) -> bytes:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Rejected("malformed_docx") from None
    with archive:
        infos = archive.infolist()
        if len(infos) > limits.max_zip_members:
            raise Rejected("too_many_zip_members")
        if sum(i.file_size for i in infos) > limits.max_uncompressed_bytes:
            raise Rejected("zip_too_large")
        for info in infos:
            if info.flag_bits & 0x1:
                raise Rejected("encrypted_docx")
            if (
                info.file_size > _MIB
                and info.file_size / max(info.compress_size, 1) > limits.max_compression_ratio
            ):
                raise Rejected("zip_ratio_too_high")
        names = {i.filename for i in infos}
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise Rejected("not_a_docx")
        # The declared sizes were checked above, and zipfile never returns more bytes than the member
        # declares (a header that lies makes the CRC check fail instead), so this read is bounded.
        try:
            with archive.open("word/document.xml") as handle:
                xml = handle.read(limits.max_uncompressed_bytes)
        except (zipfile.BadZipFile, RuntimeError, OSError, EOFError):
            raise Rejected("malformed_docx") from None
        return xml


def docx_blocks(data: bytes, limits: ExtractionLimits) -> list[Block]:
    xml = _read_document_xml(data, limits)
    if xml[:2] in (b"\xff\xfe", b"\xfe\xff") or _DOCTYPE.search(xml):
        raise Rejected("unsafe_xml")
    blocks: list[Block] = []
    depth = 0
    table_depth = 0
    rows: list[str] = []
    cells: list[str] = []
    cell_paragraphs: list[str] = []
    parts: list[str] = []
    style = ""
    numbered = False
    hidden = False
    try:
        for event, el in ET.iterparse(io.BytesIO(xml), events=("start", "end")):  # noqa: S314 - DOCTYPE and ENTITY refused above
            tag = el.tag
            if event == "start":
                depth += 1
                if depth > limits.max_xml_depth:
                    raise Rejected("xml_too_deep")
                if tag == f"{_W}p":
                    parts, style, numbered = [], "", False
                elif tag == f"{_W}pStyle":
                    style = el.get(f"{_W}val", "")
                elif tag == f"{_W}numPr":
                    numbered = True
                elif tag == f"{_W}r":
                    hidden = False
                elif tag == f"{_W}vanish":
                    hidden = el.get(f"{_W}val", "true") not in ("0", "false", "off")
                elif tag == f"{_W}tbl":
                    table_depth += 1
                    if table_depth == 1:
                        rows = []
                elif tag == f"{_W}tr" and table_depth == 1:
                    cells = []
                elif tag == f"{_W}tc" and table_depth == 1:
                    cell_paragraphs = []
                continue
            depth -= 1
            if tag == f"{_W}t" and not hidden and el.text:
                parts.append(el.text)
            elif tag in (f"{_W}tab", f"{_W}br", f"{_W}cr"):
                parts.append(" " if tag == f"{_W}tab" else "\n")
            elif tag == f"{_W}p":
                text = "".join(parts).strip()
                if text and table_depth:
                    cell_paragraphs.append(text)
                elif text:
                    blocks.append(_paragraph(text, style, numbered))
                parts = []
            elif tag == f"{_W}tc" and table_depth == 1:
                cells.append(" ".join(" ".join(cell_paragraphs).split()))
            elif tag == f"{_W}tr" and table_depth == 1:
                rows.append(" | ".join(cells))
            elif tag == f"{_W}tbl":
                table_depth -= 1
                if table_depth == 0 and any(r.strip(" |") for r in rows):
                    blocks.append(Block("table", "\n".join(rows)))
            el.clear()
    except ET.ParseError:
        raise Rejected("malformed_docx") from None
    return blocks


def _paragraph(text: str, style: str, numbered: bool) -> Block:
    match = _STYLE_HEADING.match(style)
    if match:
        return Block("heading", text, level=int(match.group(1)))
    if style == "Title":
        return Block("heading", text, level=1)
    return Block("list_item" if numbered else "paragraph", text)
