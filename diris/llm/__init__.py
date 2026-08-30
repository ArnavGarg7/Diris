"""Provider-agnostic LLM layer (Anthropic / Groq / Gemini) with fallback.

Use `get_llm()` to obtain the configured provider. `LLM` is kept as a
backward-compatible alias for the Anthropic client.
"""
from .anthropic_llm import AnthropicLLM
from .base import BaseLLM, parse_json
from .provider import get_extraction_llm, get_llm, set_llm

# Backward-compat alias (older modules did `from ..llm import LLM`).
LLM = AnthropicLLM

__all__ = [
    "BaseLLM", "parse_json", "get_llm", "get_extraction_llm", "set_llm",
    "AnthropicLLM", "LLM",
]
