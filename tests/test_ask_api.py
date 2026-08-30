"""End-to-end: upload -> processing -> POST /ask. Needs live MySQL.
Injects temp Chroma stores, a fake extractor, and a fake LLM (no network)."""
import json
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
from diris.llm import set_llm
from diris.llm.base import BaseLLM
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
        return Extraction(entities=[ExEntity(name="Moon", type="OBJECT", description="")], relationships=[])


class FakeLLM(BaseLLM):
    name = "fake"

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        return json.dumps({
            "answer": "Neil Armstrong walked on the Moon.",
            "answered": True, "confidence": 0.9, "citations": [1],
            "reasoning": "Stated in the evidence.",
        })


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
    set_llm(None)


def _auth(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_ask_returns_grounded_answer():
    headers = _auth("ask@x.com")
    set_extractor(FakeExtractor())
    r = client.post(
        "/documents",
        files={"file": ("moon.txt", b"Neil Armstrong walked on the Moon in 1969.", "text/plain")},
        headers=headers,
    )
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"

    set_llm(FakeLLM())
    res = client.post("/ask", json={"question": "who walked on the moon"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["answered"] is True
    assert "Armstrong" in body["answer"]
    assert body["citations"]  # cited a real chunk
    cite = body["citations"][0]
    assert cite["document_name"] == "moon.txt"
    assert "chunk_id" in cite and "snippet" in cite


def test_ask_with_empty_library_says_not_found():
    headers = _auth("empty@x.com")
    res = client.post("/ask", json={"question": "anything"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["answered"] is False


def test_ask_requires_auth():
    assert client.post("/ask", json={"question": "x"}).status_code == 401
