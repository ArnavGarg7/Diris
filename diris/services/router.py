"""Conversation router — one LLM 'understanding' step (inspired by the Speed AI
chatbot). It decides whether a message is small talk or a real document question,
and for real questions produces a self-contained ENGLISH query (folding in
reference-resolution + translation), so the grounded pipeline stays language- and
context-aware without hardcoded language tables.
"""
from __future__ import annotations

import logging

from ..llm import get_llm
from ..llm.base import parse_json
from .persona import persona

log = logging.getLogger("diris.router")

CONVERSATIONAL = "conversational"
DOCUMENT_QUERY = "document_query"


def route_message(history: str, message: str) -> dict:
    """Return {category, query, reply}.

    category = 'document_query' -> `query` is a self-contained English question.
    category = 'conversational' -> `reply` is a warm reply in the user's language.
    """
    prompt = _build_prompt(history, message)
    try:
        raw = get_llm().complete(prompt, system=persona())
    except Exception as exc:  # noqa: BLE001 — LLM unavailable
        log.warning("router: LLM unavailable: %s", exc)
        return {
            "category": CONVERSATIONAL,
            "query": None,
            "reply": "I'm having trouble reaching the AI service right now. Please try again in a moment.",
        }

    parsed = _safe_parse(raw)
    if parsed is None:
        # Model replied but not as JSON — its text is almost always a fine reply.
        return {"category": CONVERSATIONAL, "query": None, "reply": raw.strip()}

    category = parsed.get("category")
    if category not in (CONVERSATIONAL, DOCUMENT_QUERY):
        category = DOCUMENT_QUERY  # default: treat as a document question
    if category == DOCUMENT_QUERY:
        return {"category": DOCUMENT_QUERY, "query": (parsed.get("query") or "").strip() or message, "reply": None}
    return {"category": CONVERSATIONAL, "query": None, "reply": (parsed.get("reply") or "").strip()}


def _safe_parse(raw: str) -> dict | None:
    try:
        result = parse_json(raw)
        return result if isinstance(result, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _build_prompt(history: str, message: str) -> str:
    return f"""The user may write in ANY language (English, Hindi, Spanish, Arabic, French, …).
ALWAYS understand the message — NEVER reply that you cannot understand it. If it is a question,
translate it into clear English for "query". Reply with ONE JSON object:
{{"category": "document_query" | "conversational", "query": "<English question or null>", "reply": "<reply or null>"}}

Choose the category:

• "document_query" — the message is a REAL QUESTION or request for information: any who/what/
  when/where/how/why question, a fact lookup, a summary, a comparison, an explanation, or a
  follow-up that refines an earlier question. Route it here EVEN IF it looks like general
  knowledge — you do NOT know what the user's documents contain, and the system will honestly
  say "not in your documents" if the answer isn't there. Set "query" to a COMPLETE,
  SELF-CONTAINED ENGLISH version of the question, resolving any references ("he", "that one",
  "those", "उनमें से") from the CONVERSATION below. Set "reply" to null.

• "conversational" — ONLY pure social messages or questions about YOU (the assistant):
  greetings, thanks, goodbye, small talk, "who are you", "what can you do", "help". These do
  NOT ask for information from documents. Set "query" to null and write "reply" in the SAME
  language as the user — warm and brief, inviting them to ask about their documents.

If unsure, choose "document_query" — never deflect a genuine question.

RULES:
- Write "reply" in the EXACT same language as the user's message. Default to English for short
  or ambiguous greetings ("hi", "ok", "thanks").
- Output ONLY the JSON object. No markdown, no extra text.

CONVERSATION SO FAR:
{history or "(none)"}

USER MESSAGE:
"{message}"

JSON:"""
