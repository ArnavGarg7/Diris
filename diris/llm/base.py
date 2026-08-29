"""Provider-agnostic LLM interface.

Every provider (Anthropic / Groq / Gemini) implements `complete`; `extract_json`
is shared and parses whatever JSON the model returns defensively.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class BaseLLM(ABC):
    name: str = "llm"

    @abstractmethod
    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        """Return the model's text completion for a single user turn."""

    def extract_json(self, user: str, system: str | None = None, max_tokens: int = 4000) -> Any:
        """Return parsed JSON. The prompt must instruct the model to emit JSON.

        max_tokens kept modest (4000) so a single request fits free-tier
        per-request token caps (e.g. Groq's 8000 TPM)."""
        return parse_json(self.complete(user, system=system, max_tokens=max_tokens))


def parse_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)  # strip code fences
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from model response:\n{text[:500]}")
