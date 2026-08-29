"""Live LLM extraction test — provider-agnostic (Groq/Gemini/Anthropic).

OFF by default (it makes a real API call and spends free-tier quota). Enable with
DIRIS_RUN_LIVE_LLM=1 and at least one provider key set."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("DIRIS_RUN_LIVE_LLM") != "1",
    reason="live LLM test disabled — set DIRIS_RUN_LIVE_LLM=1 to run",
)


def test_llm_extractor_finds_expected_entities():
    from diris.extraction.llm_extractor import LLMEntityExtractor

    extractor = LLMEntityExtractor()  # uses the configured provider
    result = extractor.extract(
        "Marie Curie discovered radium while working at the University of Paris."
    )
    names = {e.name.lower() for e in result.entities}
    assert any("curie" in n for n in names)
    for rel in result.relationships:
        assert 0.0 <= rel.confidence <= 1.0
