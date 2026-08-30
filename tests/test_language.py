"""Offline language detection tests (deterministic via DetectorFactory seed)."""
from diris.services.language import detect_language, language_name


def test_detects_english():
    assert detect_language("The quick brown fox jumps over the lazy dog every day.") == "en"


def test_detects_hindi():
    assert detect_language("नमस्ते, आप कैसे हैं? यह एक हिंदी परीक्षण वाक्य है।") == "hi"


def test_short_or_empty_defaults_to_english():
    assert detect_language("") == "en"
    assert detect_language("ok") == "en"


def test_language_name_lookup():
    assert language_name("hi") == "Hindi"
    assert language_name("en") == "English"
    assert language_name("xx") == "xx"  # unknown code passes through
