"""Chooses the LLM provider(s) from configured keys. Test-injectable."""
from __future__ import annotations

from ..config import settings
from .base import BaseLLM

_llm: BaseLLM | None = None
_extraction_llm: BaseLLM | None = None

_DEFAULT_ORDER = ["groq", "gemini", "anthropic"]


def _order_for(pref: str) -> list[str]:
    pref = pref.lower()
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


def _build_chain(order: list[str]) -> BaseLLM:
    chain = [c for c in (_make(p) for p in order) if c is not None]
    if not chain:
        raise RuntimeError(
            "No LLM provider configured. Set GROQ_API_KEY, GEMINI_API_KEY, or "
            "ANTHROPIC_API_KEY in your .env."
        )
    from .fallback import FallbackLLM

    return chain[0] if len(chain) == 1 else FallbackLLM(chain)


def get_llm() -> BaseLLM:
    """The general-purpose LLM (routing, QA, translation)."""
    global _llm
    if _llm is None:
        _llm = _build_chain(_order_for(settings.llm_provider))
    return _llm


def get_extraction_llm() -> BaseLLM:
    """The LLM used for bulk entity extraction — prefers a fast, high-limit
    provider (Gemini flash-lite by default) so multi-chunk documents don't
    stall on the slower general-purpose model. Falls back to the others."""
    global _extraction_llm
    if _extraction_llm is None:
        _extraction_llm = _build_chain(_order_for(settings.extraction_provider))
    return _extraction_llm


def set_llm(llm: BaseLLM | None) -> None:
    """Inject a provider (tests) or reset to None to rebuild lazily. Also clears
    the extraction LLM so both are rebuilt from current config/injection."""
    global _llm, _extraction_llm
    _llm = llm
    _extraction_llm = llm
