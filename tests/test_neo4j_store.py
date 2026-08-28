"""Unit tests for Neo4jGraphStore. Skipped if Neo4j isn't reachable."""
import pytest

from diris.config import settings


def _neo4j_reachable() -> bool:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _neo4j_reachable(), reason="Neo4j not reachable — `docker compose up -d neo4j`"
)


@pytest.fixture
def store():
    from diris.graph.neo4j_store import Neo4jGraphStore

    s = Neo4jGraphStore()
    s.clear()
    yield s
    s.clear()
    s.close()


def test_upsert_entities_and_relationship_then_neighborhood(store):
    store.upsert_entity(1, 100, "NASA", "ORGANIZATION")
    store.upsert_entity(2, 100, "Apollo", "EVENT")
    store.upsert_relationship(
        rel_id=10, user_id=100, source_id=1, target_id=2, type="runs",
        confidence=0.9, evidence="NASA ran Apollo", document_id=5, chunk_id=7,
    )

    sub = store.neighborhood(100, 1, hops=1)
    assert sub is not None
    assert {n["name"] for n in sub["nodes"]} >= {"NASA", "Apollo"}
    assert len(sub["edges"]) == 1
    assert sub["edges"][0]["type"] == "runs"


def test_relationship_merge_is_idempotent(store):
    store.upsert_entity(1, 100, "A", "T")
    store.upsert_entity(2, 100, "B", "T")
    for _ in range(2):  # same rel_id -> MERGE matches, no duplicate
        store.upsert_relationship(
            rel_id=10, user_id=100, source_id=1, target_id=2, type="rel",
            confidence=0.5, evidence=None, document_id=5, chunk_id=7,
        )
    assert len(store.neighborhood(100, 1, hops=1)["edges"]) == 1


def test_delete_document_relationships(store):
    store.upsert_entity(1, 100, "A", "T")
    store.upsert_entity(2, 100, "B", "T")
    store.upsert_relationship(
        rel_id=10, user_id=100, source_id=1, target_id=2, type="rel",
        confidence=0.5, evidence=None, document_id=5, chunk_id=7,
    )
    store.delete_document_relationships(5)
    assert store.neighborhood(100, 1, hops=1)["edges"] == []


def test_missing_entity_returns_none(store):
    assert store.neighborhood(100, 9999, hops=1) is None
