"""Split raw document text into overlapping chunks.

Chunks are the unit of retrieval and provenance: every extracted entity,
relationship, and cited answer traces back to a chunk id. Each chunk also
records the section it came from (nearest markdown/HTML heading) so citations
can point the user at *where* in the document a fact appears.
"""
from __future__ import annotations

import re

from ..config import settings

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)")
_HTML_HEADING = re.compile(r"^<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE)


def _detect_heading(paragraph: str) -> str | None:
    """Return a section title if this paragraph's first line is a heading."""
    first_line = paragraph.strip().splitlines()[0].strip() if paragraph.strip() else ""
    md = _MD_HEADING.match(first_line)
    if md:
        return md.group(2).strip()[:255]
    html = _HTML_HEADING.match(first_line)
    if html:
        return re.sub(r"<[^>]+>", "", html.group(1)).strip()[:255]
    return None


def chunk_text_with_sections(
    text: str,
    chunk_chars: int | None = None,
    overlap: int | None = None,
) -> list[tuple[str, str | None]]:
    """Paragraph-aware sliding-window chunker that also tracks the current section.

    Returns a list of (chunk_text, section) pairs. `section` is the nearest
    preceding heading, or None for formats/positions without one.
    """
    chunk_chars = chunk_chars or settings.chunk_chars
    overlap = overlap or settings.chunk_overlap

    text = re.sub(r"[ \t]+", " ", text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[tuple[str, str | None]] = []
    buffer = ""
    buffer_section: str | None = None
    current_section: str | None = None

    for para in paragraphs:
        heading = _detect_heading(para)
        if heading is not None:
            current_section = heading

        if not buffer:
            buffer_section = current_section

        if len(buffer) + len(para) + 1 <= chunk_chars:
            buffer = f"{buffer}\n{para}" if buffer else para
        else:
            if buffer:
                chunks.append((buffer, buffer_section))
            if len(para) > chunk_chars:
                for piece in _hard_split(para, chunk_chars, overlap):
                    chunks.append((piece, current_section))
                buffer = ""
                buffer_section = None
            else:
                tail = buffer[-overlap:] if buffer else ""
                buffer = f"{tail}\n{para}".strip() if tail else para
                buffer_section = current_section
    if buffer:
        chunks.append((buffer, buffer_section))
    return chunks


def chunk_text(
    text: str,
    chunk_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Backward-compatible: just the chunk texts (drops section info)."""
    return [t for t, _ in chunk_text_with_sections(text, chunk_chars, overlap)]


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    out, start = [], 0
    while start < len(text):
        end = start + size
        out.append(text[start:end])
        start = end - overlap
    return out
