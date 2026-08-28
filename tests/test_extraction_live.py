"""Live LLM extraction test. Runs ONLY if ANTHROPIC_API_KEY is set (costs a
small amount). Verifies the real extractor returns sensible entities."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live LLM extraction test",
)


def test_llm_extractor_finds_expected_entities():
    from diris.extraction.llm_extractor import LLMEntityExtractor

    extractor = LLMEntityExtractor()
    result = extractor.extract(
        "Marie Curie discovered radium while working at the University of Paris."
    )
    names = {e.name.lower() for e in result.entities}
    assert any("curie" in n for n in names)
    # Extraction should be structurally valid.
    for rel in result.relationships:
        assert 0.0 <= rel.confidence <= 1.0
