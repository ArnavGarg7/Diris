"""Grounded QA + conversational routing with seeded evidence + a fake LLM.
Real MySQL + Chroma, no network. Skipped if MySQL isn't reachable."""
import json

import pytest
from sqlalchemy import delete, text

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
from diris.db.repositories import ChunkRepository, DocumentRepository, UserRepository
from diris.db.session import Base, SessionLocal, engine
from diris.llm import set_llm
from diris.llm.base import BaseLLM
from diris.security import hash_password
from diris.services.qa import answer_question
from diris.vectorstore import set_entity_index, set_vector_store


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="MySQL not reachable")


class FakeLLM(BaseLLM):
    """Handles both the router call and the grounded-answer call.

    The router prompt is detected by the '"category"' marker; everything else is
    treated as the grounded-answer prompt.
    """

    name = "fake"

    def __init__(self, answer_payload: dict | None = None, route: dict | None = None):
        self._answer = answer_payload or {
            "answer": "(default)", "answered": True, "confidence": 0.5,
            "citations": [], "reasoning": "x",
        }
        self._route = route or {"category": "document_query", "query": None, "reply": None}
        self.prompts: list[str] = []

    def complete(self, user: str, system: str | None = None, max_tokens: int = 4000) -> str:
        self.prompts.append(user)
        if '"category"' in user:  # router prompt
            return json.dumps(self._route)
        return json.dumps(self._answer)


def _wipe(db) -> None:
    for model in (Relationship, EntityMention, EntityAlias, Entity, Chunk,
                  DocumentMetadata, Document, User):
        db.execute(delete(model))
    db.commit()


@pytest.fixture
def seed(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    vstore = ChromaVectorStore(persist_dir=str(tmp_path / "chunks"), collection_name="test_chunks")
    set_vector_store(vstore)
    set_entity_index(ChromaVectorStore(persist_dir=str(tmp_path / "entities"), collection_name="test_entities"))
    set_llm(FakeLLM())  # default fake so routing never hits a real provider

    Base.metadata.create_all(engine)
    db = SessionLocal()
    _wipe(db)

    user = UserRepository(db).create("qa@x.com", hash_password("secret123"))
    doc = DocumentRepository(db).create(
        user_id=user.id, original_filename="d.txt", stored_path="/fake/d.txt",
        content_type="text/plain", size_bytes=10,
    )
    chunks = ChunkRepository(db).add_chunks(
        doc.id,
        ["Neil Armstrong walked on the Moon in 1969.", "Bananas are rich in potassium."],
    )
    c0, c1 = [c.id for c in chunks]
    vstore.upsert(
        ids=[str(c.id) for c in chunks],
        texts=[c.content for c in chunks],
        metadatas=[{"user_id": user.id, "document_id": doc.id, "chunk_index": c.chunk_index} for c in chunks],
    )

    yield {"db": db, "user": user, "c0": c0, "c1": c1}

    _wipe(db)
    db.close()
    set_vector_store(None)
    set_entity_index(None)
    set_llm(None)


def test_grounded_answer_maps_citations_to_real_chunks(seed):
    set_llm(FakeLLM(answer_payload={
        "answer": "Neil Armstrong walked on the Moon in 1969.",
        "answered": True, "confidence": 0.9, "citations": [1],
        "reasoning": "Chunk 1 states it directly.",
    }))
    ans = answer_question(seed["db"], seed["user"], "who walked on the moon")
    assert ans.answered is True
    assert ans.citations
    assert {c.chunk_id for c in ans.citations} <= {seed["c0"], seed["c1"]}
    assert ans.citations[0].document_name == "d.txt"
    assert ans.citations[0].snippet


def test_no_evidence_returns_answered_false(seed):
    other = UserRepository(seed["db"]).create("empty@x.com", hash_password("secret123"))
    ans = answer_question(seed["db"], other, "anything at all")
    assert ans.answered is False
    assert ans.citations == []


def test_llm_insufficient_evidence_passes_through(seed):
    set_llm(FakeLLM(answer_payload={
        "answer": "The documents don't cover the capital of France.",
        "answered": False, "confidence": 0.1, "citations": [],
        "reasoning": "Not present in the evidence.",
    }))
    ans = answer_question(seed["db"], seed["user"], "what is the capital of France")
    assert ans.answered is False
    assert ans.confidence < 0.5
    assert ans.citations == []


def test_conversational_message_returns_warm_reply_without_retrieval(seed):
    fake = FakeLLM(route={"category": "conversational", "query": None, "reply": "Hi! Ask me about your documents."})
    set_llm(fake)
    ans = answer_question(seed["db"], seed["user"], "hello there")
    assert ans.answered is True
    assert ans.answer == "Hi! Ask me about your documents."
    assert ans.citations == []
    assert len(fake.prompts) == 1  # only the router ran — no grounded-answer call


def test_answer_language_override_reaches_the_prompt(seed):
    fake = FakeLLM(answer_payload={
        "answer": "respuesta", "answered": True, "confidence": 0.8, "citations": [1], "reasoning": "x",
    })
    set_llm(fake)
    answer_question(seed["db"], seed["user"], "who walked on the moon", answer_language="Spanish")
    assert "Spanish" in fake.prompts[-1]  # the grounded-answer prompt targets Spanish
