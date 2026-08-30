"""Language detection + translation for multilingual QA (M11).

Detection uses langdetect (offline, no torch). Translation uses the configured
LLM (Groq/Gemini) — the "translation pivot" that lets an English-centric
embedder retrieve English chunks for a non-English query.
"""
from __future__ import annotations

from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0  # deterministic detection

_LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian",
    "zh-cn": "Chinese", "zh-tw": "Chinese", "ja": "Japanese", "ko": "Korean",
    "ar": "Arabic", "bn": "Bengali", "ta": "Tamil", "te": "Telugu",
    "ur": "Urdu", "pa": "Punjabi", "gu": "Gujarati", "mr": "Marathi",
}


def detect_language(text: str) -> str:
    """Return an ISO language code (e.g. 'en', 'hi'). Defaults to 'en'."""
    text = (text or "").strip()
    if len(text) < 3:
        return "en"
    try:
        return detect(text)
    except Exception:  # noqa: BLE001 — ambiguous/empty input
        return "en"


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, code)


def translate_to_english(text: str) -> str:
    """Translate arbitrary text to English via the LLM (for retrieval)."""
    from ..llm import get_llm

    prompt = (
        "Translate the following text to English. "
        "Return ONLY the translation, with no quotes or commentary.\n\n"
        f"{text}"
    )
    return get_llm().complete(prompt).strip() or text
