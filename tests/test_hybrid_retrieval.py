"""Hybrid retrieval with a directly-seeded knowledge base (real MySQL + Chroma,
no LLM). Verifies each retriever contributes and provenance is tracked.
Skipped if MySQL isn't reachable.
"""
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
from diris.db.repositories import (
    ChunkRepository,
    DocumentRepository,
    EntityRepository,
    UserRepository,
)
from diris.db.session import Base, SessionLocal, engine
from diris.security import hash_password
from diris.services.retrieval import hybrid_search
from diris.vectorstore import set_entity_index, set_vector_store


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="MySQL not reachable")


def _wipe(db) -> None:
    for model in (Relationship, EntityMention, EntityAlias, Entity, Chunk,
                  DocumentMetadata, Document, User):
        db.execute(delete(model))
    db.commit()


@pytest.fixture
def seed(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    vstore = ChromaVectorStore(persist_dir=str(tmp_path / "chunks"), collection_name="test_chunks")
    eindex = ChromaVectorStore(persist_dir=str(tmp_path / "entities"), collection_name="test_entities")
    set_vector_store(vstore)
    set_entity_index(eindex)

    Base.metadata.create_all(engine)
    db = SessionLocal()
    _wipe(db)

    user = UserRepository(db).create("hybrid@x.com", hash_password("secret123"))
    doc = DocumentRepository(db).create(
        user_id=user.id, original_filename="d.txt", stored_path="/fake/d.txt",
        content_type="text/plain", size_bytes=10,
    )
    texts = [
        "Neil Armstrong walked on the Moon during the Apollo 11 mission.",  # c0
        "The Saturn V rocket propelled the mission into orbit.",            # c1
        "Bananas are a good dietary source of potassium.",                 # c2
    ]
    chunks = ChunkRepository(db).add_chunks(doc.id, texts)
    c0, c1, c2 = [c.id for c in chunks]

    # InnoDB holds new rows in an in-memory FULLTEXT cache that isn't searchable
    # until synced; force it so the keyword retriever is deterministic in tests.
    db.execute(text("OPTIMIZE TABLE chunks"))
    db.commit()

    # Embed the chunks (vector retriever).
    vstore.upsert(
        ids=[str(c.id) for c in chunks],
        texts=[c.content for c in chunks],
        metadatas=[{"user_id": user.id, "document_id": doc.id, "chunk_index": c.chunk_index} for c in chunks],
    )

    # Entities + mentions (graph retriever seed + provenance).
    erepo = EntityRepository(db)
    apollo = erepo.create(user_id=user.id, canonical_name="Apollo 11", normalized_name="apollo 11", type="EVENT")
    saturn = erepo.create(user_id=user.id, canonical_name="Saturn V", normalized_name="saturn v", type="TECHNOLOGY")
    erepo.add_mention(apollo.id, c0, doc.id, "Apollo 11")
    erepo.add_mention(saturn.id, c1, doc.id, "Saturn V")
    db.commit()
    eindex.upsert(
        ids=[str(apollo.id), str(saturn.id)],
        texts=["Apollo 11", "Saturn V"],
        metadatas=[{"user_id": user.id, "type": "EVENT", "entity_id": apollo.id},
                   {"user_id": user.id, "type": "TECHNOLOGY", "entity_id": saturn.id}],
    )

    yield {"db": db, "user": user, "c0": c0, "c1": c1, "c2": c2}

    _wipe(db)
    db.close()
    set_vector_store(None)
    set_entity_index(None)


def test_vector_signal_finds_paraphrase(seed):
    results = hybrid_search(seed["db"], seed["user"], "who stepped onto the lunar surface", top_k=5)
    hit = next((r for r in results if r.chunk_id == seed["c0"]), None)
    assert hit is not None
    assert "vector" in hit.sources


def test_keyword_signal_matches_terms(seed):
    results = hybrid_search(seed["db"], seed["user"], "Saturn rocket orbit", top_k=5)
    hit = next((r for r in results if r.chunk_id == seed["c1"]), None)
    assert hit is not None
    assert "keyword" in hit.sources


def test_graph_signal_surfaces_entity_chunks(seed):
    # Query is about Apollo 11; the graph retriever pulls chunks that mention the
    # seeded entities (incl. Saturn V's chunk) even without lexical overlap.
    results = hybrid_search(seed["db"], seed["user"], "Apollo 11", top_k=5)
    hit = next((r for r in results if r.chunk_id == seed["c1"]), None)
    assert hit is not None
    assert "graph" in hit.sources
