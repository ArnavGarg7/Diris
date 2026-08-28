"""The extractor interface. Lets us swap the real LLM extractor for a fake in
tests (keeping the test suite free and deterministic)."""
from __future__ import annotations

from typing import Protocol

from .schema import Extraction


class EntityExtractor(Protocol):
    def extract(self, text: str) -> Extraction:
        """Return entities + relationships found in a chunk of text."""
        ...
