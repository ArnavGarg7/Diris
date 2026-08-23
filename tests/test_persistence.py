"""Save/load roundtrips for the graph and vector stores.

`tmp_path` is a pytest fixture giving a fresh temp directory per test, so these
never touch the real data/store.
"""
from diris.graph import KnowledgeGraph
from diris.vectorstore import Chunk, VectorStore


def test_graph_roundtrip(tmp_path):
    kg = KnowledgeGraph()
    kg.add_entity("Marie Curie", "PERSON", chunk_id="d::0")
    kg.add_entity("Radium", "CONCEPT", chunk_id="d::0")
    kg.add_relationship("Marie Curie", "Radium", "discovered", chunk_id="d::0")

    path = tmp_path / "graph.json"
    kg.save(path)
    reloaded = KnowledgeGraph.load(path)

    assert reloaded.stats() == kg.stats()
    assert reloaded.nodes["marie curie"]["mentions"] == {"d::0"}
    assert reloaded.edges[0]["provenance"] == {"d::0"}


def test_vector_roundtrip(tmp_path):
    vs = VectorStore()
    vs.add(Chunk(id="d::0", doc="d", text="alpha beta gamma"))

    path = tmp_path / "vectors.json"
    vs.save(path)
    reloaded = VectorStore.load(path)

    assert len(reloaded.chunks) == 1
    assert reloaded.search("alpha")[0][0].id == "d::0"


def test_load_missing_file_returns_empty_stores(tmp_path):
    assert KnowledgeGraph.load(tmp_path / "nope.json").stats()["entities"] == 0
    assert VectorStore.load(tmp_path / "nope.json").chunks == []
