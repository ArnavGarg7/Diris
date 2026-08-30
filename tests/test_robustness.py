"""Robustness / failure-mode tests (offline). The system must not trust the LLM
blindly and must handle malformed / empty inputs gracefully."""
import pytest

from diris.extraction.extractor import _coerce
from diris.ingestion import chunk_text
from diris.llm.base import parse_json


def test_extraction_drops_relationships_with_unknown_endpoints():
    data = {
        "entities": [{"name": "Alice", "type": "PERSON"}],
        "relationships": [{"source": "Alice", "target": "Ghost", "type": "knows"}],
    }
    ext = _coerce(data)
    assert [e.name for e in ext.entities] == ["Alice"]
    assert ext.relationships == []  # target not among extracted entities -> dropped


def test_extraction_ignores_malformed_rows():
    data = {
        "entities": [{"name": "Bob", "type": "PERSON"}, {"nope": "x"}],
        "relationships": ["garbage", {"source": "Bob", "target": "Bob", "type": "self"}],
    }
    ext = _coerce(data)  # must not raise
    assert [e.name for e in ext.entities] == ["Bob"]  # malformed entity dropped


def test_parse_json_recovers_from_fences_and_noise():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"b": 2} hope that helps') == {"b": 2}
    with pytest.raises(ValueError):
        parse_json("there is no json here at all")


def test_empty_document_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []


def test_qa_prompt_instructs_conflict_handling():
    from diris.services.qa import _build_prompt

    prompt = _build_prompt("Who discovered it?", ["[1] A did", "[2] B did"], [], "English")
    assert "CONTRADICT" in prompt.upper()  # both viewpoints must be surfaced
