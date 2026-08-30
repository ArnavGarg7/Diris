"""Groq provider (OpenAI-compatible chat completions; fast, free tier)."""
from __future__ import annotations

from ..config import settings
from .base import BaseLLM


class GroqLLM(BaseLLM):
    name = "groq"

    def __init__(self, model: str | None = None):
        from groq import Groq

        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        self.model = model or settings.groq_model
        # timeout: a hung request fails instead of freezing the worker.
        # max_retries: the SDK backs off on 429/5xx (Groq free-tier rate limits).
        self.client = Groq(
            api_key=settings.groq_api_key,
            timeout=float(settings.llm_timeout_seconds),
            max_retries=2,
        )

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,  # deterministic-ish for extraction
        )
        return (resp.choices[0].message.content or "").strip()
