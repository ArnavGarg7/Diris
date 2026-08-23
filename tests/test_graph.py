"""KnowledgeGraph merge/traversal behaviour."""
from diris.graph import KnowledgeGraph


def test_entities_dedupe_by_normalized_name():
    kg = KnowledgeGraph()
    kg.add_entity("Neil Armstrong", "PERSON", chunk_id="d::0")
    kg.add_entity("neil armstrong", chunk_id="d::1")  # same normalized id
    assert kg.stats()["entities"] == 1
    node = kg.nodes["neil armstrong"]
    assert node["mentions"] == {"d::0", "d::1"}  # provenance from both mentions kept


def test_relationship_needs_both_endpoints():
    kg = KnowledgeGraph()
    kg.add_entity("A")
    kg.add_entity("B")
    kg.add_relationship("A", "B", "related_to", chunk_id="d::0")
    kg.add_relationship("A", "ghost", "related_to")  # target missing -> dropped
    assert kg.stats()["relationships"] == 1


def test_neighborhood_and_find_entities():
    kg = KnowledgeGraph()
    kg.add_entity("NASA", "ORGANIZATION")
    kg.add_entity("Apollo", "EVENT")
    kg.add_relationship("NASA", "Apollo", "runs")
    sub = kg.neighborhood(["nasa"], hops=1)
    assert "apollo" in sub["nodes"]
    assert kg.find_entities("Tell me about NASA") == ["nasa"]


def test_duplicate_relationship_accumulates_confidence():
    kg = KnowledgeGraph()
    kg.add_entity("X")
    kg.add_entity("Y")
    kg.add_relationship("X", "Y", "related_to", confidence=0.7, chunk_id="d::0")
    kg.add_relationship("X", "Y", "related_to", confidence=0.7, chunk_id="d::1")
    assert kg.stats()["relationships"] == 1  # merged, not duplicated
    edge = kg.edges[0]
    assert edge["provenance"] == {"d::0", "d::1"}
    assert edge["confidence"] > 0.7
