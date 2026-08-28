"""End-to-end: upload -> processing -> GET /search/hybrid. Needs live MySQL.
Injects temp Chroma stores + a fake extractor (no LLM)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from diris.api.main import app
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
from diris.vectorstore import set_entity_index, set_vector_store


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="MySQL not reachable")

client = TestClient(app)


class FakeExtractor:
    def extract(self, text_: str) -> Extraction:
        return Extraction(
            entities=[
                ExEntity(name="Apollo", type="EVENT", description="Moon program"),
                ExEntity(name="NASA", type="ORGANIZATION", description="space agency"),
            ],
            relationships=[
                ExRel(source="NASA", target="Apollo", type="runs", evidence="", confidence=0.9),
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
    from diris.vectorstore.chroma_store import ChromaVectorStore

    set_vector_store(ChromaVectorStore(persist_dir=str(tmp_path / "chunks"), collection_name="test_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=str(tmp_path / "entities"), collection_name="test_entities"))
    Base.metadata.create_all(engine)
    _wipe()
    yield
    _wipe()
    set_vector_store(None)
    set_entity_index(None)


def _auth(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_hybrid_search_returns_ranked_results_with_provenance():
    headers = _auth("hy@x.com")
    set_extractor(FakeExtractor())
    r = client.post(
        "/documents",
        files={"file": ("moon.txt", b"NASA ran the Apollo program to land astronauts on the Moon.", "text/plain")},
        headers=headers,
    )
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"

    res = client.get("/search/hybrid", params={"q": "astronauts landing on the Moon"}, headers=headers)
    assert res.status_code == 200
    results = res.json()
    assert results
    assert all("sources" in r for r in results)
    assert any("vector" in r["sources"] or "keyword" in r["sources"] for r in results)


def test_hybrid_search_is_user_scoped():
    a = _auth("alice@x.com")
    set_extractor(FakeExtractor())
    client.post("/documents", files={"file": ("a.txt", b"Alice notes on rockets and space.", "text/plain")}, headers=a)

    b = _auth("bob@x.com")
    assert client.get("/search/hybrid", params={"q": "rockets"}, headers=b).json() == []


def test_hybrid_search_requires_auth():
    assert client.get("/search/hybrid", params={"q": "x"}).status_code == 401
