"""Shared test fixtures.

By default, inject a no-op entity extractor so NO test accidentally calls the
Anthropic API (which costs money and is non-deterministic). Tests that want to
exercise extraction set their own fake extractor in the test body; the live LLM
test constructs the real extractor directly.
"""
import pytest

from diris.extraction import set_extractor
from diris.extraction.schema import Extraction


class _NoOpExtractor:
    def extract(self, text: str) -> Extraction:
        return Extraction(entities=[], relationships=[])


@pytest.fixture(autouse=True)
def no_llm_extractor_by_default():
    set_extractor(_NoOpExtractor())
    yield
    set_extractor(None)  # reset to the real (lazily-built) extractor
