"""LLM-backed entity extractor (the default). Uses the configured extraction
model (claude-sonnet-5 by default) and the existing extraction prompt."""
from __future__ import annotations

from ..config import settings
from ..llm import LLM
from .extractor import extract_knowledge
from .schema import Extraction


class LLMEntityExtractor:
    def __init__(self, model: str | None = None):
        # LLM() validates the API key; if absent it raises here (handled upstream
        # as a best-effort extraction failure — chunks/embeddings still succeed).
        self.llm = LLM(model or settings.extraction_model)

    def extract(self, text: str) -> Extraction:
        return extract_knowledge(text, llm=self.llm)
