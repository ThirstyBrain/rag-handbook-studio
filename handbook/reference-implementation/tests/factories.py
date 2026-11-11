"""Builders for test documents: Word files, PDFs, and hostile variants. Everything is generated here so
no binary fixture is checked in and every file's content is visible in the test that uses it."""

from __future__ import annotations

import io
import struct
import zipfile
from collections.abc import Sequence

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
    'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>'
)


def docx(body_xml: str, *, document_prefix: str = "") -> bytes:
    """A minimal .docx whose word/document.xml wraps ``body_xml`` (WordprocessingML paragraphs)."""
    document = (
        f'<?xml version="1.0" encoding="UTF-8"?>{document_prefix}'
        f'<w:document xmlns:w="{W}"><w:body>{body_xml}</w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", document)
    return buffer.getvalue()


def para(text: str, *, style: str = "", numbered: bool = False, hidden: bool = False) -> str:
    ppr = ""
    if style or numbered:
        ppr = "<w:pPr>"
        ppr += f'<w:pStyle w:val="{style}"/>' if style else ""
        ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>' if numbered else ""
        ppr += "</w:pPr>"
    rpr = "<w:rPr><w:vanish/></w:rPr>" if hidden else ""
    return f"<w:p>{ppr}<w:r>{rpr}<w:t>{text}</w:t></w:r></w:p>"


def table(rows: Sequence[Sequence[str]]) -> str:
    cells = "".join(
        "<w:tr>" + "".join(f"<w:tc>{para(c)}</w:tc>" for c in row) + "</w:tr>" for row in rows
    )
    return f"<w:tbl>{cells}</w:tbl>"


def zip_with(members: dict[str, bytes], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buffer.getvalue()


def zip_with_lying_sizes(real_size: int, declared_size: int) -> bytes:
    """A docx whose zip headers declare a smaller uncompressed size than the data really has."""
    data = zip_with(
        {
            "[Content_Types].xml": _CONTENT_TYPES.encode(),
            "word/document.xml": b"<w:document xmlns:w='x'>" + b"A" * real_size + b"</w:document>",
        }
    )
    patched = bytearray(data)
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        start = 0
        while (at := patched.find(signature, start)) != -1:
            patched[at + offset : at + offset + 4] = struct.pack("<I", declared_size)
            start = at + 4
    return bytes(patched)


def pdf(pages: Sequence[str]) -> bytes:
    """A valid PDF with one line of Helvetica text per page."""
    n = len(pages)
    font = 3 + 2 * n
    objs: dict[int, bytes] = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    for i, text in enumerate(pages):
        page_id = 3 + 2 * i
        content_id = page_id + 1
        objs[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>"
        ).encode()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
        objs[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    objs[font] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objs):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objs[number] + b"\nendobj\n"
    xref_at = len(out)
    size = max(objs) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for number in range(1, size):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def encrypted_pdf(pages: Sequence[str]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf(pages))))
    writer.encrypt("secret", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
