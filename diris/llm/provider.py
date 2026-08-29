"""Chooses the LLM provider(s) from configured keys. Test-injectable."""
from __future__ import annotations

from ..config import settings
from .base import BaseLLM

_llm: BaseLLM | None = None

_DEFAULT_ORDER = ["groq", "gemini", "anthropic"]


def _provider_order() -> list[str]:
    pref = settings.llm_provider.lower()
    if pref in _DEFAULT_ORDER:  # explicit choice first, others as fallback
        return [pref] + [p for p in _DEFAULT_ORDER if p != pref]
    return _DEFAULT_ORDER  # "auto"


def _make(provider: str) -> BaseLLM | None:
    """Construct a provider client, or None if its key is missing."""
    try:
        if provider == "groq" and settings.groq_api_key:
            from .groq_llm import GroqLLM

            return GroqLLM()
        if provider == "gemini" and settings.gemini_api_key:
            from .gemini_llm import GeminiLLM

            return GeminiLLM()
        if provider == "anthropic" and settings.api_key:
            from .anthropic_llm import AnthropicLLM

            return AnthropicLLM()
    except Exception:  # noqa: BLE001 — a missing SDK / bad key just drops the provider
        return None
    return None


def get_llm() -> BaseLLM:
    global _llm
    if _llm is not None:
        return _llm
    chain = [c for c in (_make(p) for p in _provider_order()) if c is not None]
    if not chain:
        raise RuntimeError(
            "No LLM provider configured. Set GROQ_API_KEY, GEMINI_API_KEY, or "
            "ANTHROPIC_API_KEY in your .env."
        )
    from .fallback import FallbackLLM

    _llm = chain[0] if len(chain) == 1 else FallbackLLM(chain)
    return _llm


def set_llm(llm: BaseLLM | None) -> None:
    """Inject a provider (tests) or reset to None to rebuild lazily."""
    global _llm
    _llm = llm
