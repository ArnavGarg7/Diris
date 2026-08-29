"""Anthropic (Claude) provider. Used only when ANTHROPIC_API_KEY is set."""
from __future__ import annotations

from ..config import settings
from .base import BaseLLM


class AnthropicLLM(BaseLLM):
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic

        self._anthropic = anthropic
        self.model = model or settings.model
        if not settings.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic()

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or self._anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
