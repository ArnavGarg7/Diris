"""TF-IDF VectorStore ranking and lookup."""
from diris.vectorstore import Chunk, VectorStore


def test_search_ranks_relevant_chunk_first():
    vs = VectorStore()
    vs.add(Chunk(id="d::0", doc="d", text="The Moon landing happened in 1969."))
    vs.add(Chunk(id="d::1", doc="d", text="Photosynthesis occurs in green plants."))
    hits = vs.search("who landed on the moon", top_k=2)
    assert hits
    assert hits[0][0].id == "d::0"


def test_empty_store_returns_empty():
    assert VectorStore().search("anything") == []


def test_get_by_id():
    vs = VectorStore()
    vs.add(Chunk(id="x::0", doc="x", text="hello world"))
    assert vs.get("x::0").text == "hello world"
    assert vs.get("missing") is None
