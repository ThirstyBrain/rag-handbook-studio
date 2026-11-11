"""Structure-aware chunking: invariants over many shapes of input (ADR-003, ADR-016).

The configuration uses chars_per_token=1 so a "token" is one character and expected sizes are easy to
read; the estimator's real default (4 characters per token) is covered by the configuration tests.
"""

from __future__ import annotations

import itertools
import re

import pytest

from rag_service.features.chunking.chunker import ChunkConfig, chunk_blocks
from rag_service.features.extraction.model import Block, Rejected


def cfg(target: int = 200, maximum: int = 300, overlap: int = 40, **kw: int) -> ChunkConfig:
    return ChunkConfig(
        target_tokens=target, max_tokens=maximum, overlap_tokens=overlap, chars_per_token=1.0, **kw
    )


def prose(n: int, start: int = 0) -> str:
    """n sentences, each carrying a unique marker such as w0007."""
    return " ".join(
        f"Sentence number {i} carries the marker w{i:04d}." for i in range(start, start + n)
    )


def markers(text: str) -> set[str]:
    return set(re.findall(r"w\d{4}", text))


# ------------------------------------------------------------------ configuration


def test_configuration_is_validated() -> None:
    for bad in (
        dict(target_tokens=100, max_tokens=50),
        dict(target_tokens=100, max_tokens=200, overlap_tokens=100),
        dict(target_tokens=100, max_tokens=200, overlap_tokens=-1),
        dict(target_tokens=100, max_tokens=200, chars_per_token=0),
        dict(target_tokens=100, max_tokens=200, max_chunks=0),
    ):
        with pytest.raises(ValueError):
            ChunkConfig(**bad)  # type: ignore[arg-type]


def test_token_estimate_uses_the_configured_ratio() -> None:
    assert ChunkConfig(chars_per_token=4.0).count("x" * 9) == 3
    assert ChunkConfig(chars_per_token=4.0).count("") == 0
    assert ChunkConfig(chars_per_token=2.0).count("x" * 9) == 5


# ------------------------------------------------------------------ size, coverage, determinism


def test_prose_and_code_chunks_never_exceed_the_target_and_tables_never_the_maximum() -> None:
    long_word = "x" * 700  # no whitespace at all: must still be cut
    config = cfg()
    flat = [
        Block("paragraph", prose(60)),
        Block("paragraph", long_word),
        Block("code", "\n".join(f"line {i} " + "y" * 90 for i in range(40))),
        Block("list_item", prose(30, 100)),
    ]
    chunks = chunk_blocks(flat, config)
    assert chunks and max(c.token_count for c in chunks) <= config.target_tokens
    table = Block("table", "H1 | H2\n" + "\n".join(f"r{i} | {'z' * 60}" for i in range(40)))
    tables = chunk_blocks([table], config)
    assert tables and max(c.token_count for c in tables) <= config.max_tokens
    assert all(
        c.content.strip() and c.token_count == config.count(c.content) for c in chunks + tables
    )


def test_oversized_sentences_are_split_down_to_the_target() -> None:
    """Units between one and three times the target (250 and 450 characters against a 200 target)
    must be split, not passed through."""
    config = cfg(overlap=0)
    for size in (250, 450):  # each is one unit: no sentence boundary, no whitespace
        chunks = chunk_blocks([Block("paragraph", "n" * size)], config)
        assert len(chunks) >= 2, f"a {size}-character unit must be split"
        assert max(c.token_count for c in chunks) <= config.target_tokens
        assert "".join(c.content for c in chunks) == "n" * size, "and nothing is lost"


def test_overlap_never_pushes_a_chunk_over_the_target() -> None:
    """A short unit before a large one is carried as overlap only if the result still fits."""
    # 10 + 1 + 195 = 206 > 200: the short unit survives as overlap only if it is dropped again
    short, long_ = "Short one.", "L" * 194 + "."
    text = " ".join([short, long_] * 6)
    config = cfg(target=200, maximum=300, overlap=40)
    chunks = chunk_blocks([Block("paragraph", text)], config)
    assert len(chunks) >= 6
    assert max(c.token_count for c in chunks) <= config.target_tokens


def test_every_marker_of_the_input_appears_in_some_chunk() -> None:
    text = prose(120)
    chunks = chunk_blocks([Block("paragraph", text)], cfg())
    seen: set[str] = set()
    for c in chunks:
        seen |= markers(c.content)
    assert seen == markers(text), "no content may be lost"


def test_same_input_and_configuration_give_identical_chunks() -> None:
    blocks = [
        Block("heading", "A", 1),
        Block("paragraph", prose(50)),
        Block("table", "h | h\na | b"),
    ]
    assert chunk_blocks(blocks, cfg()) == chunk_blocks(blocks, cfg())


def test_ordinals_are_contiguous_from_zero_across_sections() -> None:
    blocks = [
        Block("heading", "One", 1),
        Block("paragraph", prose(30)),
        Block("heading", "Two", 1),
        Block("paragraph", prose(30, 50)),
    ]
    assert [c.ordinal for c in chunk_blocks(blocks, cfg())] == list(
        range(len(chunk_blocks(blocks, cfg())))
    )


# ------------------------------------------------------------------ sections


def test_a_chunk_never_spans_two_sections_and_carries_its_section_path() -> None:
    blocks = [
        Block("heading", "Policy", 1),
        Block("paragraph", prose(10, 0)),
        Block("heading", "Leave", 2),
        Block("paragraph", prose(10, 100)),
        Block("heading", "Parental", 3),
        Block("paragraph", prose(10, 200)),
        Block("heading", "Expenses", 2),
        Block("paragraph", prose(10, 300)),
        Block("heading", "Other", 1),
        Block("paragraph", prose(10, 400)),
    ]
    chunks = chunk_blocks(blocks, cfg())
    paths = {c.section_path for c in chunks}
    assert paths == {
        "Policy",
        "Policy > Leave",
        "Policy > Leave > Parental",
        "Policy > Expenses",
        "Other",
    }
    for c in chunks:
        numbers = {int(m[1:]) // 100 for m in markers(c.content)}
        assert len(numbers) == 1, f"chunk mixes sections: {c.section_path}"


def test_content_before_the_first_heading_has_an_empty_path_and_empty_sections_vanish() -> None:
    blocks = [
        Block("paragraph", "preamble text"),
        Block("heading", "Empty", 1),
        Block("heading", "Full", 1),
        Block("paragraph", "body"),
    ]
    assert [(c.section_path, c.content) for c in chunk_blocks(blocks, cfg())] == [
        ("", "preamble text"),
        ("Full", "body"),
    ]


def test_headings_only_produce_no_chunks() -> None:
    assert chunk_blocks([Block("heading", "A", 1), Block("heading", "B", 2)], cfg()) == []
    assert chunk_blocks([], cfg()) == []


def test_heading_level_skips_are_handled() -> None:
    blocks = [
        Block("heading", "H1", 1),
        Block("heading", "H3", 3),
        Block("paragraph", "x"),
        Block("heading", "H2", 2),
        Block("paragraph", "y"),
    ]
    assert [c.section_path for c in chunk_blocks(blocks, cfg())] == ["H1 > H3", "H1 > H2"]


# ------------------------------------------------------------------ overlap


def test_overlap_repeats_trailing_sentences_within_a_section_only() -> None:
    blocks = [
        Block("heading", "A", 1),
        Block("paragraph", prose(40)),
        Block("heading", "B", 1),
        Block("paragraph", prose(40, 500)),
    ]
    chunks = chunk_blocks(blocks, cfg(overlap=60))
    a = [c for c in chunks if c.section_path == "A"]
    b = [c for c in chunks if c.section_path == "B"]
    assert len(a) > 2 and len(b) > 2
    for first, second in itertools.pairwise(a):
        assert markers(first.content) & markers(second.content), "consecutive chunks share overlap"
    assert not markers(a[-1].content) & markers(b[0].content), "overlap never crosses a heading"


def test_no_overlap_when_disabled() -> None:
    chunks = chunk_blocks([Block("paragraph", prose(60))], cfg(overlap=0))
    for first, second in itertools.pairwise(chunks):
        assert not markers(first.content) & markers(second.content)


def test_overlap_never_exceeds_its_budget() -> None:
    config = cfg(overlap=60)
    chunks = chunk_blocks([Block("paragraph", prose(80))], config)
    for first, second in itertools.pairwise(chunks):
        shared = markers(first.content) & markers(second.content)
        # each sentence is about 45 characters, so at most one whole sentence fits in 60
        assert len(shared) <= 1


# ------------------------------------------------------------------ boundaries and structure


def test_chunks_of_prose_end_on_sentence_boundaries() -> None:
    chunks = chunk_blocks([Block("paragraph", prose(60))], cfg(overlap=0))
    assert all(c.content.endswith(".") for c in chunks)
    assert all(c.content.startswith("Sentence") for c in chunks)


def test_a_table_that_spans_chunks_repeats_its_header_row() -> None:
    rows = "\n".join(f"row{i:03d} | value {i}" for i in range(60))
    chunks = chunk_blocks([Block("table", "Name | Amount\n" + rows)], cfg(overlap=0))
    assert len(chunks) > 3
    assert all(c.content.startswith("Name | Amount\n") for c in chunks), (
        "every chunk keeps the header"
    )
    assert all(c.content.count("Name | Amount") == 1 for c in chunks), "and shows it only once"
    seen = [r for c in chunks for r in re.findall(r"row\d{3}", c.content)]
    assert seen == [f"row{i:03d}" for i in range(60)], "every row appears exactly once, in order"


def test_a_header_too_large_to_repeat_is_not_repeated_rather_than_breaking_the_size_cap() -> None:
    header = "H" * 150  # more than a quarter of the target
    rows = "\n".join(f"row{i:03d} " + "v" * 60 for i in range(30))
    config = cfg(target=200, maximum=300, overlap=0)
    chunks = chunk_blocks([Block("table", header + "\n" + rows)], config)
    assert max(c.token_count for c in chunks) <= config.max_tokens
    assert sum(c.content.count(header) for c in chunks) == 1


def test_code_blocks_keep_their_line_structure() -> None:
    code = "\n".join(f"step_{i}()" for i in range(50))
    chunks = chunk_blocks([Block("code", code)], cfg(overlap=0))
    assert "\n".join(c.content for c in chunks) == code


def test_list_items_start_on_their_own_line() -> None:
    chunks = chunk_blocks(
        [Block("paragraph", "Intro."), Block("list_item", "first"), Block("list_item", "second")],
        cfg(),
    )
    assert len(chunks) == 1 and chunks[0].content == "Intro.\nfirst\nsecond"


def test_paragraphs_are_separated_by_a_blank_line() -> None:
    chunks = chunk_blocks([Block("paragraph", "One."), Block("paragraph", "Two.")], cfg())
    assert chunks[0].content == "One.\n\nTwo."


# ------------------------------------------------------------------ pages and limits


def test_page_range_is_the_min_and_max_of_its_blocks() -> None:
    blocks = [Block("paragraph", prose(3), page=2), Block("paragraph", prose(3, 10), page=3)]
    (chunk,) = chunk_blocks(blocks, cfg(target=2000, maximum=3000, overlap=0))
    assert (chunk.page_start, chunk.page_end) == (2, 3)
    (plain,) = chunk_blocks([Block("paragraph", "no pages here")], cfg())
    assert (plain.page_start, plain.page_end) == (None, None)


def test_a_document_that_would_make_too_many_chunks_is_rejected() -> None:
    blocks = [
        Block("heading", f"S{i}", 1) if j == 0 else Block("paragraph", "text")
        for i in range(30)
        for j in (0, 1)
    ]
    with pytest.raises(Rejected) as info:
        chunk_blocks(blocks, cfg(max_chunks=10))
    assert info.value.reason == "too_many_chunks"
