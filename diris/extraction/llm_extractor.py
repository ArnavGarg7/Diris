"""LLM-backed entity extractor (the default). Uses the configured provider
(Groq/Gemini/Anthropic via get_llm) and the existing extraction prompt."""
from __future__ import annotations

from ..llm import get_extraction_llm
from .extractor import extract_knowledge
from .schema import Extraction


class LLMEntityExtractor:
    def __init__(self):
        # get_extraction_llm() picks the extraction provider (fast/high-limit by
        # default); if no key is set it raises here (handled upstream as
        # best-effort — chunks/embeddings still succeed).
        self.llm = get_extraction_llm()

    def extract(self, text: str) -> Extraction:
        return extract_knowledge(text, llm=self.llm)
