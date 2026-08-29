"""Google Gemini provider (google-genai SDK)."""
from __future__ import annotations

from ..config import settings
from .base import BaseLLM


class GeminiLLM(BaseLLM):
    name = "gemini"

    def __init__(self, model: str | None = None):
        from google import genai

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model = model or settings.gemini_model
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            max_output_tokens=max_tokens,
            temperature=0,
        )
        resp = self.client.models.generate_content(
            model=self.model, contents=user, config=config
        )
        return (resp.text or "").strip()
