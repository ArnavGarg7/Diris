"""Thin wrapper around the Anthropic Messages API.

Two capabilities the pipeline needs:
  * extract_json  -> ask Claude for a JSON payload and parse it defensively
  * complete      -> a plain text completion (used for question answering)
"""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from .config import settings


class LLM:
    def __init__(self, model: str | None = None):
        self.model = model or settings.model
        # Zero-arg client resolves ANTHROPIC_API_KEY / auth profile automatically.
        settings.require_key()
        self.client = anthropic.Anthropic()

    # -- low level ---------------------------------------------------------
    def complete(
        self,
        user: str,
        system: str | None = None,
        max_tokens: int = 4000,
        effort: str = "high",
    ) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    # -- structured extraction --------------------------------------------
    def extract_json(
        self,
        user: str,
        system: str | None = None,
        max_tokens: int = 8000,
        effort: str = "low",
    ) -> Any:
        """Return parsed JSON. The prompt must instruct Claude to emit JSON only."""
        raw = self.complete(user, system=system, max_tokens=max_tokens, effort=effort)
        return _parse_json(raw)


def _parse_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from model response:\n{text[:500]}")
