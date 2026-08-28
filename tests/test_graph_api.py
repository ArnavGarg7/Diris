"""Integration: upload -> extract (fake) -> project to Neo4j -> neighborhood API.

Needs live MySQL AND Neo4j. Injects temp Chroma stores, a fake extractor, and a
cleared Neo4j so nothing touches real data.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from diris.api.main import app
from diris.config import settings
from diris.db import models  # noqa: F401
from diris.db.models import (
    Chunk,
    Document,
    DocumentMetadata,
    Entity,
    EntityAlias,
    EntityMention,
    Relationship,
    User,
)
from diris.db.session import Base, SessionLocal, engine
from diris.extraction import set_extractor
from diris.extraction.schema import Entity as ExEntity
from diris.extraction.schema import Extraction
from diris.extraction.schema import Relationship as ExRel
from diris.graph import set_graph_store
from diris.vectorstore import set_entity_index, set_vector_store


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _neo4j_reachable() -> bool:
    try:
        from neo4j import GraphDatabase

        d = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        d.verify_connectivity()
        d.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_db_reachable() and _neo4j_reachable()),
    reason="needs live MySQL + Neo4j",
)

client = TestClient(app)


class FakeExtractor:
    def extract(self, text_: str) -> Extraction:
        return Extraction(
            entities=[
                ExEntity(name="NASA", type="ORGANIZATION", description="space agency"),
                ExEntity(name="Apollo", type="EVENT", description="Moon program"),
            ],
            relationships=[
                ExRel(source="NASA", target="Apollo", type="runs",
                      evidence="NASA ran Apollo", confidence=0.9),
            ],
        )


def _wipe() -> None:
    with SessionLocal() as db:
        for doc in db.execute(select(Document)).scalars():
            Path(doc.stored_path).unlink(missing_ok=True)
        for model in (Relationship, EntityMention, EntityAlias, Entity, Chunk,
                      DocumentMetadata, Document, User):
            db.execute(delete(model))
        db.commit()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path):
    from diris.graph.neo4j_store import Neo4jGraphStore
    from diris.vectorstore.chroma_store import ChromaVectorStore

    set_vector_store(ChromaVectorStore(persist_dir=str(tmp_path / "chunks"), collection_name="test_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=str(tmp_path / "entities"), collection_name="test_entities"))
    graph = Neo4jGraphStore()
    graph.clear()
    set_graph_store(graph)
    Base.metadata.create_all(engine)
    _wipe()
    yield
    _wipe()
    graph.clear()
    graph.close()
    set_vector_store(None)
    set_entity_index(None)
    set_graph_store(None)


def _auth(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload_and_wait(headers) -> None:
    set_extractor(FakeExtractor())
    r = client.post(
        "/documents",
        files={"file": ("moon.txt", b"Apollo was run by NASA.", "text/plain")},
        headers=headers,
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"


def test_neighborhood_reflects_projected_graph():
    headers = _auth("graph@x.com")
    _upload_and_wait(headers)

    entities = client.get("/entities", headers=headers).json()
    nasa = next(e for e in entities if e["canonical_name"] == "NASA")

    res = client.get(f"/entities/{nasa['id']}/neighborhood", params={"hops": 1}, headers=headers)
    assert res.status_code == 200
    sub = res.json()
    assert {n["name"] for n in sub["nodes"]} >= {"NASA", "Apollo"}
    assert any(e["type"] == "runs" for e in sub["edges"])


def test_neighborhood_is_user_scoped():
    a = _auth("alice@x.com")
    _upload_and_wait(a)
    a_entity_id = client.get("/entities", headers=a).json()[0]["id"]

    b = _auth("bob@x.com")
    assert client.get(
        f"/entities/{a_entity_id}/neighborhood", headers=b
    ).status_code == 404


def test_neighborhood_requires_auth():
    assert client.get("/entities/1/neighborhood").status_code == 401
