"""Graph visualization + export endpoints (M14). Needs live MySQL + Neo4j."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from diris.api.main import app
from diris.config import settings
from diris.db import models  # noqa: F401
from diris.db.models import User
from diris.db.session import Base, SessionLocal, engine
from diris.graph import set_graph_store


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
    not (_db_reachable() and _neo4j_reachable()), reason="needs live MySQL + Neo4j"
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def graph_env():
    from diris.graph.neo4j_store import Neo4jGraphStore

    store = Neo4jGraphStore()
    store.clear()
    set_graph_store(store)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
    yield store
    store.clear()
    store.close()
    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
    set_graph_store(None)


def _auth_and_uid(email: str):
    reg = client.post("/auth/register", json={"email": email, "password": "secret123"})
    uid = reg.json()["id"]
    tok = client.post("/auth/login", data={"username": email, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, uid


def _seed_graph(store, uid: int):
    store.upsert_entity(1, uid, "NASA", "ORGANIZATION")
    store.upsert_entity(2, uid, "Apollo", "EVENT")
    store.upsert_entity(3, uid, "Saturn V", "TECHNOLOGY")
    store.upsert_relationship(rel_id=10, user_id=uid, source_id=1, target_id=2, type="runs",
                              confidence=0.9, evidence="", document_id=5, chunk_id=7)
    store.upsert_relationship(rel_id=11, user_id=uid, source_id=2, target_id=3, type="uses",
                              confidence=0.8, evidence="", document_id=5, chunk_id=8)


def test_full_graph_returns_user_nodes_and_edges(graph_env):
    headers, uid = _auth_and_uid("g@x.com")
    _seed_graph(graph_env, uid)
    g = client.get("/graph", headers=headers).json()
    assert {n["name"] for n in g["nodes"]} >= {"NASA", "Apollo", "Saturn V"}
    assert any(e["type"] == "runs" for e in g["edges"])


def test_shortest_path_between_entities(graph_env):
    headers, uid = _auth_and_uid("g@x.com")
    _seed_graph(graph_env, uid)
    # NASA(1) -> Apollo(2) -> Saturn V(3): a 2-hop path
    res = client.get("/graph/path", params={"source_id": 1, "target_id": 3}, headers=headers).json()
    assert res["found"] is True
    assert {n["entity_id"] for n in res["nodes"]} == {1, 2, 3}


def test_export_graphml(graph_env):
    headers, uid = _auth_and_uid("g@x.com")
    _seed_graph(graph_env, uid)
    r = client.get("/graph/export", params={"format": "graphml"}, headers=headers)
    assert r.status_code == 200
    assert "<graphml" in r.text
    assert "NASA" in r.text


def test_graph_is_user_scoped(graph_env):
    a_headers, a_uid = _auth_and_uid("alice@x.com")
    _seed_graph(graph_env, a_uid)
    b_headers, _ = _auth_and_uid("bob@x.com")
    assert client.get("/graph", headers=b_headers).json()["nodes"] == []


def test_view_page_and_auth():
    r = client.get("/graph/view")  # HTML page itself is public (a dev tool)
    assert r.status_code == 200
    assert "vis-network" in r.text
    # data endpoints require auth
    assert client.get("/graph").status_code == 401
