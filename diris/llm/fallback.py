"""Fallback wrapper: try providers in order until one succeeds.

Free-tier providers rate-limit and occasionally error; this makes the second
key an actual backup rather than dead config.
"""
from __future__ import annotations

import logging

from .base import BaseLLM

log = logging.getLogger("diris.llm")


class FallbackLLM(BaseLLM):
    name = "fallback"

    def __init__(self, providers: list[BaseLLM]):
        assert providers, "FallbackLLM needs at least one provider"
        self.providers = providers

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return provider.complete(user, system=system, max_tokens=max_tokens)
            except Exception as exc:  # noqa: BLE001 — try the next provider
                log.warning("LLM provider %s failed: %s", provider.name, exc)
                last_error = exc
        raise RuntimeError(f"All LLM providers failed; last error: {last_error}")
