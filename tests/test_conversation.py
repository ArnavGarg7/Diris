"""Conversation memory (M12): repo, contextualization, and multi-turn /ask.
Needs live MySQL. Injects temp Chroma stores + fake extractor/LLM (no network)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from diris.api.main import app
from diris.db import models  # noqa: F401
from diris.db.models import (
    Chunk,
    Conversation,
    Document,
    DocumentMetadata,
    Entity,
    EntityAlias,
    EntityMention,
    Message,
    Relationship,
    User,
)
from diris.db.repositories import ConversationRepository, UserRepository
from diris.db.session import Base, SessionLocal, engine
from diris.extraction import set_extractor
from diris.extraction.schema import Entity as ExEntity
from diris.extraction.schema import Extraction
from diris.llm import set_llm
from diris.llm.base import BaseLLM
from diris.security import hash_password
from diris.services.conversation import contextualize
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

    def __init__(self):
        self.prompts: list[str] = []

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        self.prompts.append(user)
        if "STANDALONE QUESTION" in user:  # contextualization call
            return "who walked on the moon"
        return json.dumps({
            "answer": "Neil Armstrong walked on the Moon.", "answered": True,
            "confidence": 0.9, "citations": [1], "reasoning": "Chunk 1.",
        })


def _wipe() -> None:
    with SessionLocal() as db:
        for doc in db.execute(select(Document)).scalars():
            Path(doc.stored_path).unlink(missing_ok=True)
        for model in (Message, Conversation, Relationship, EntityMention, EntityAlias,
                      Entity, Chunk, DocumentMetadata, Document, User):
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


# -- unit-ish ---------------------------------------------------------------
def test_repository_orders_and_isolates():
    with SessionLocal() as db:
        user = UserRepository(db).create("conv@x.com", hash_password("secret123"))
        repo = ConversationRepository(db)
        conv = repo.create(user.id)
        repo.add_message(conv.id, "user", "Q1")
        repo.add_message(conv.id, "assistant", "A1")
        msgs = repo.messages(conv.id)
        assert [m.role for m in msgs] == ["user", "assistant"]
        # isolation
        other = UserRepository(db).create("other@x.com", hash_password("secret123"))
        assert repo.get_for_user(conv.id, other.id) is None


def test_contextualize_no_history_returns_question():
    assert contextualize([], "What house is he in?") == "What house is he in?"


def test_contextualize_rewrites_with_history():
    fake = FakeLLM()
    set_llm(fake)
    history = [
        Message(conversation_id=1, role="user", content="Who is Harry Potter?"),
        Message(conversation_id=1, role="assistant", content="A student at Hogwarts."),
    ]
    out = contextualize(history, "What house is he in?")
    assert out == "who walked on the moon"  # fake rewrite
    assert any("STANDALONE QUESTION" in p for p in fake.prompts)


# -- API multi-turn ---------------------------------------------------------
def test_multi_turn_flow_persists_and_contextualizes():
    headers = _auth("chat@x.com")
    set_extractor(FakeExtractor())
    r = client.post(
        "/documents",
        files={"file": ("moon.txt", b"Neil Armstrong walked on the Moon in 1969.", "text/plain")},
        headers=headers,
    )
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"

    cid = client.post("/conversations", headers=headers).json()["id"]
    fake = FakeLLM()
    set_llm(fake)

    r1 = client.post("/ask", json={"question": "Who walked on the moon?", "conversation_id": cid}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["conversation_id"] == cid

    r2 = client.post("/ask", json={"question": "Tell me more about him.", "conversation_id": cid}, headers=headers)
    assert r2.status_code == 200
    # The second turn triggered a contextualization rewrite.
    assert any("STANDALONE QUESTION" in p for p in fake.prompts)

    detail = client.get(f"/conversations/{cid}", headers=headers).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][0]["content"] == "Who walked on the moon?"


def test_conversation_is_user_scoped():
    a = _auth("alice@x.com")
    cid = client.post("/conversations", headers=a).json()["id"]
    b = _auth("bob@x.com")
    assert client.get(f"/conversations/{cid}", headers=b).status_code == 404
    assert client.post(
        "/ask", json={"question": "hi", "conversation_id": cid}, headers=b
    ).status_code == 404


def test_conversations_require_auth():
    assert client.post("/conversations").status_code == 401
    assert client.get("/conversations").status_code == 401
