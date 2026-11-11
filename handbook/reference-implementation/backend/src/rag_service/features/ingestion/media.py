"""Content-type detection for uploads. The client's declared type is never trusted on its own.

An upload is accepted only if its *content* matches an allow-listed type and the declared type (if any)
agrees with the content. Detection looks at the first bytes only; real parsing happens in extraction
(component 4), which must still treat the file as hostile.
"""

from __future__ import annotations

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_TYPES = frozenset({"text/plain", "text/markdown", "text/html"})
ALLOWED = frozenset({PDF, DOCX}) | TEXT_TYPES
HEAD_BYTES = 8192


_ALLOWED_CONTROLS = frozenset(b"\t\n\r\x0c")


def _looks_like_text(head: bytes) -> bool:
    # Real text has no NUL, no DEL and no C0 control characters other than tab, newline, carriage
    # return and form feed. (A bare executable magic number such as b"\x7fELF" is valid UTF-8.)
    if any((b < 0x20 and b not in _ALLOWED_CONTROLS) or b == 0x7F for b in head):
        return False
    for cut in range(0, 4):  # the head may end in the middle of a multi-byte character
        try:
            (head[: len(head) - cut] if cut else head).decode("utf-8")
            return True
        except UnicodeDecodeError:
            continue
    return False


def detect_media_type(head: bytes, declared: str | None) -> str | None:
    """Return the accepted media type, or None if the content is not allowed or contradicts the declaration."""
    declared_type = (declared or "").split(";", 1)[0].strip().lower() or None
    if declared_type is not None and declared_type not in ALLOWED | {"application/octet-stream"}:
        return None
    if head.startswith(b"%PDF-"):
        return PDF if declared_type in (None, PDF, "application/octet-stream") else None
    if head.startswith(b"PK\x03\x04"):
        # A zip container. We only admit it as a Word document, and only if the client said so.
        return DOCX if declared_type == DOCX else None
    if not head or not _looks_like_text(head):
        return None
    if declared_type in TEXT_TYPES:
        return declared_type
    return "text/plain" if declared_type in (None, "application/octet-stream") else None
