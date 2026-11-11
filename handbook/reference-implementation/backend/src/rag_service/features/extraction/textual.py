"""Plain text, Markdown and HTML to structural blocks, using the standard library only.

HTML handling is deliberately conservative: script, style, template and similar elements are dropped
along with comments, and no attribute value (alt, title, href) becomes text. Text hidden by CSS cannot be
detected without rendering; that is a documented residual risk (ADR-016).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from rag_service.features.extraction.model import Block

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t#]*$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_LIST = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])[ \t]+(.*)$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _table_row(line: str) -> str:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return " | ".join(cells)


def plain_text_blocks(text: str) -> list[Block]:
    """Paragraphs separated by blank lines."""
    return [Block("paragraph", p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def markdown_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []
    code: list[str] | None = None
    table: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(Block("paragraph", "\n".join(paragraph).strip()))
            paragraph.clear()

    def flush_table() -> None:
        if table:
            blocks.append(Block("table", "\n".join(table)))
            table.clear()

    for line in text.split("\n"):
        if code is not None:
            if _FENCE.match(line):
                blocks.append(Block("code", "\n".join(code)))
                code = None
            else:
                code.append(line)
            continue
        if _FENCE.match(line):
            flush_paragraph()
            flush_table()
            code = []
            continue
        if line.lstrip().startswith("|") and line.count("|") >= 2:
            flush_paragraph()
            if not _TABLE_SEPARATOR.match(line):
                table.append(_table_row(line))
            continue
        flush_table()
        heading = _HEADING.match(line)
        item = _LIST.match(line)
        if heading:
            flush_paragraph()
            blocks.append(Block("heading", heading.group(2).strip(), level=len(heading.group(1))))
        elif item:
            flush_paragraph()
            blocks.append(Block("list_item", item.group(1).strip()))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.strip())
    if code:  # an unterminated fence still carries content
        blocks.append(Block("code", "\n".join(code)))
    flush_paragraph()
    flush_table()
    return [b for b in blocks if b.text.strip()]


_SKIP = frozenset(
    {"script", "style", "template", "noscript", "head", "svg", "iframe", "object", "math"}
)
_BLOCKS = frozenset(
    {"p", "div", "section", "article", "main", "header", "footer", "aside", "nav", "blockquote",
     "ul", "ol", "dl", "dt", "dd", "figure", "figcaption", "form", "fieldset", "address", "body", "html"}
)  # fmt: skip
_HEADINGS = {f"h{n}": n for n in range(1, 7)}
_MAX_DEPTH = 500


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._buf: list[str] = []
        self._skip_depth = 0
        self._depth = 0
        self._kind = "paragraph"
        self._level = 0
        self._pre = 0
        self._table_depth = 0
        self._rows: list[str] = []
        self._cells: list[str] = []

    # -- text assembly ---------------------------------------------------------------
    def _flush(self) -> None:
        raw = "".join(self._buf)
        self._buf.clear()
        text = raw.strip("\n") if self._kind == "code" else " ".join(raw.split())
        if text.strip():
            self.blocks.append(Block(self._kind, text, self._level))
        self._kind, self._level = "paragraph", 0

    def _flush_cell(self) -> None:
        raw = " ".join("".join(self._buf).split())
        self._buf.clear()
        self._cells.append(raw)

    def _flush_row(self) -> None:
        if self._cells:
            self._rows.append(" | ".join(self._cells))
            self._cells = []

    # -- parser callbacks ------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        if self._depth > _MAX_DEPTH:
            raise RecursionError("html nesting too deep")
        if tag in _SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            if not self._table_depth:
                self._flush()
            self._table_depth += 1
        elif tag in ("td", "th") and self._table_depth:
            self._buf.append("")
        elif tag == "tr" and self._table_depth:
            self._flush_row()
        elif self._table_depth:
            return
        elif tag in _HEADINGS:
            self._flush()
            self._kind, self._level = "heading", _HEADINGS[tag]
        elif tag == "li":
            self._flush()
            self._kind = "list_item"
        elif tag == "pre":
            self._flush()
            self._kind, self._pre = "code", self._pre + 1
        elif tag == "br":
            self._buf.append("\n" if self._pre else " ")
        elif tag in _BLOCKS:
            self._flush()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        self._depth = max(0, self._depth - 1)
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ("td", "th") and self._table_depth:
            self._flush_cell()
        elif tag == "tr" and self._table_depth:
            self._flush_row()
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if not self._table_depth:
                self._flush_row()
                if self._rows:
                    self.blocks.append(Block("table", "\n".join(self._rows)))
                self._rows = []
                self._buf.clear()
        elif self._table_depth:
            return
        elif tag in _HEADINGS or tag in ("li", "pre") or tag in _BLOCKS:
            if tag == "pre":
                self._pre = max(0, self._pre - 1)
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        if self._table_depth:  # unterminated table
            self._table_depth = 0
            if "".join(self._buf).strip():
                self._flush_cell()
            self._flush_row()
            if self._rows:
                self.blocks.append(Block("table", "\n".join(self._rows)))
        self._flush()


def html_blocks(text: str) -> list[Block]:
    parser = _Collector()
    parser.feed(text)
    parser.close()
    return parser.blocks
