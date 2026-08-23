"""Split raw document text into overlapping chunks.

Chunks are the unit of retrieval and provenance: every extracted entity,
relationship, and cited answer traces back to a chunk id.
"""
from __future__ import annotations

import re

from ..config import settings


def chunk_text(
    text: str,
    chunk_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Paragraph-aware sliding window chunker.

    We first normalise whitespace, then greedily pack paragraphs into windows
    of ~chunk_chars, carrying `overlap` characters of tail context into the
    next window so sentences that straddle a boundary are not lost.
    """
    chunk_chars = chunk_chars or settings.chunk_chars
    overlap = overlap or settings.chunk_overlap

    text = re.sub(r"[ \t]+", " ", text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= chunk_chars:
            buffer = f"{buffer}\n{para}" if buffer else para
        else:
            if buffer:
                chunks.append(buffer)
            # A single paragraph larger than the window gets hard-split.
            if len(para) > chunk_chars:
                chunks.extend(_hard_split(para, chunk_chars, overlap))
                buffer = ""
            else:
                tail = buffer[-overlap:] if buffer else ""
                buffer = f"{tail}\n{para}".strip() if tail else para
    if buffer:
        chunks.append(buffer)
    return chunks


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    out, start = [], 0
    while start < len(text):
        end = start + size
        out.append(text[start:end])
        start = end - overlap
    return out
