"""Chunker behaviour. Pure-Python — no API key or network needed."""
from diris.ingestion import chunk_text, chunk_text_with_sections


def test_chunks_are_nonempty():
    chunks = chunk_text("Paragraph one.\n\nParagraph two.", chunk_chars=100, overlap=10)
    assert chunks
    assert all(c.strip() for c in chunks)


def test_long_text_splits_into_multiple_chunks():
    text = "\n\n".join(f"Paragraph number {i} with some filler words." for i in range(50))
    chunks = chunk_text(text, chunk_chars=200, overlap=40)
    assert len(chunks) > 1


def test_single_oversized_paragraph_is_hard_split_within_bounds():
    # One paragraph, no blank lines, larger than the window -> hard split.
    para = "word " * 500  # ~2500 chars
    chunks = chunk_text(para, chunk_chars=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_sections_track_nearest_markdown_heading():
    text = (
        "# Introduction\n\nThis is the intro paragraph.\n\n"
        "## Details\n\nHere are the details of the topic.\n\n"
        "Even more details follow here."
    )
    sectioned = chunk_text_with_sections(text, chunk_chars=60, overlap=10)
    # Map each chunk to its section; every non-heading body chunk should carry one.
    sections = {section for _, section in sectioned}
    assert "Introduction" in sections
    assert "Details" in sections


def test_sections_are_none_without_headings():
    text = "Just a plain paragraph.\n\nAnother plain paragraph with no headings."
    sectioned = chunk_text_with_sections(text)
    assert all(section is None for _, section in sectioned)
