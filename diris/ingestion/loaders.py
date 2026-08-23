"""Document loaders. Turns a file on disk into plain text.

Built-in formats (no extra deps): .txt .md .markdown .html .htm
Optional formats (install the noted package): .pdf (pypdf), .docx (python-docx)

Each optional loader degrades gracefully with a clear message if the
dependency is missing, so the pipeline never hard-crashes on one bad file.
"""
from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
HTML_SUFFIXES = {".html", ".htm"}


class UnsupportedFormat(Exception):
    pass


def load_document(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in HTML_SUFFIXES:
        return _load_html(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    raise UnsupportedFormat(
        f"Unsupported file type '{suffix}' for {path.name}. "
        f"Supported: {sorted(TEXT_SUFFIXES | HTML_SUFFIXES) + ['.pdf', '.docx']}"
    )


def _load_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    except ImportError:
        # Crude tag strip when beautifulsoup4 isn't installed.
        import re

        return re.sub(r"<[^>]+>", " ", raw)


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise UnsupportedFormat(
            "PDF support needs pypdf. Install it with:  pip install pypdf"
        ) from e
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _load_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as e:
        raise UnsupportedFormat(
            "DOCX support needs python-docx. Install it with:  pip install python-docx"
        ) from e
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)
