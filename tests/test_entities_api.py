"""Integration: upload -> processing extracts (fake extractor) -> entities API.

Needs live MySQL. Injects temp Chroma stores + a fake extractor so no LLM is
called and nothing touches real data.
"""
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


def _upload_and_wait(headers) -> int:
    set_extractor(FakeExtractor())  # set in body to beat the autouse no-op default
    r = client.post(
        "/documents",
        files={"file": ("moon.txt", b"Apollo was run by NASA to reach the Moon.", "text/plain")},
        headers=headers,
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"
    return doc_id


def test_entities_extracted_and_listed():
    headers = _auth("ent@x.com")
    doc_id = _upload_and_wait(headers)

    entities = client.get("/entities", headers=headers).json()
    names = {e["canonical_name"] for e in entities}
    assert {"NASA", "Apollo"} <= names

    doc_entities = client.get(f"/documents/{doc_id}/entities", headers=headers).json()
    assert {e["canonical_name"] for e in doc_entities} == {"NASA", "Apollo"}

    nasa = next(e for e in entities if e["canonical_name"] == "NASA")
    detail = client.get(f"/entities/{nasa['id']}", headers=headers).json()
    assert detail["mention_count"] >= 1
    assert any(r["type"] == "runs" for r in detail["relationships"])


def test_entities_are_user_scoped():
    a = _auth("alice@x.com")
    b = _auth("bob@x.com")
    _upload_and_wait(a)
    a_entity_id = client.get("/entities", headers=a).json()[0]["id"]

    assert client.get("/entities", headers=b).json() == []
    assert client.get(f"/entities/{a_entity_id}", headers=b).status_code == 404


def test_entities_require_auth():
    assert client.get("/entities").status_code == 401
