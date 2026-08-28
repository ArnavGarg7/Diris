"""Process-wide accessor for the entity extractor (test-injectable)."""
from __future__ import annotations

from .base import EntityExtractor

_extractor: EntityExtractor | None = None


def get_extractor() -> EntityExtractor:
    global _extractor
    if _extractor is None:
        from .llm_extractor import LLMEntityExtractor  # lazy: constructs the LLM client

        _extractor = LLMEntityExtractor()
    return _extractor


def set_extractor(extractor: EntityExtractor | None) -> None:
    global _extractor
    _extractor = extractor
