"""Entity resolution + extraction orchestration (real MySQL + real embeddings,
NO LLM). Deterministic by controlling the resolver's similarity threshold and
using a fake extractor. Skipped if MySQL isn't reachable.
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
    RelationshipRepository,
    UserRepository,
)
from diris.db.session import Base, SessionLocal, engine
from diris.extraction.schema import Entity as ExEntity
from diris.extraction.schema import Extraction
from diris.extraction.schema import Relationship as ExRel
from diris.security import hash_password
from diris.services.resolution import EntityResolver


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
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    _wipe(session)
    yield session
    _wipe(session)
    session.close()


@pytest.fixture
def index(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    return ChromaVectorStore(
        persist_dir=str(tmp_path / "entities"), collection_name="test_entities"
    )


@pytest.fixture
def ctx(db):
    """A user + document + one chunk, so mentions have valid foreign keys."""
    user = UserRepository(db).create("res@x.com", hash_password("secret123"))
    doc = DocumentRepository(db).create(
        user_id=user.id, original_filename="d.txt", stored_path="/fake/d.txt",
        content_type="text/plain", size_bytes=10,
    )
    chunk = ChunkRepository(db).add_chunks(doc.id, ["some text"])[0]
    return {"user_id": user.id, "document_id": doc.id, "chunk_id": chunk.id}


def _resolve(resolver, ctx, name, type, description=None):
    return resolver.resolve(
        user_id=ctx["user_id"], name=name, type=type, description=description,
        chunk_id=ctx["chunk_id"], document_id=ctx["document_id"],
    )


def test_exact_normalized_name_merges(db, index, ctx):
    r = EntityResolver(db, index, threshold=0.99)  # high -> embedding won't merge
    e1 = _resolve(r, ctx, "NASA", "ORGANIZATION", "space agency")
    e2 = _resolve(r, ctx, "nasa", "ORGANIZATION")  # same normalized name
    assert e1.id == e2.id
    assert len(EntityRepository(db).get(e1.id).mentions) == 2  # provenance from both


def test_distinct_entities_stay_separate(db, index, ctx):
    r = EntityResolver(db, index, threshold=0.99)
    a = _resolve(r, ctx, "NASA", "ORGANIZATION")
    b = _resolve(r, ctx, "Marie Curie", "PERSON")
    assert a.id != b.id


def test_embedding_merge_records_alias(db, index, ctx):
    r = EntityResolver(db, index, threshold=0.0)  # any similarity merges
    e1 = _resolve(r, ctx, "NASA", "ORGANIZATION")
    e2 = _resolve(r, ctx, "Space Agency", "ORGANIZATION")  # different surface, same type
    assert e1.id == e2.id
    aliases = [a.alias for a in EntityRepository(db).get(e1.id).aliases]
    assert "Space Agency" in aliases


def test_type_guard_blocks_cross_type_embedding_merge(db, index, ctx):
    r = EntityResolver(db, index, threshold=0.0)
    a = _resolve(r, ctx, "Apollo", "EVENT")
    b = _resolve(r, ctx, "Artemis", "PERSON")  # only EVENT indexed -> filtered out
    assert a.id != b.id


def test_orphan_entities_are_deleted(db, index, ctx):
    r = EntityResolver(db, index, threshold=0.99)
    entity = _resolve(r, ctx, "Temporary", "CONCEPT")
    eid = entity.id  # capture before commit expires the instance
    # Remove its mentions, then run orphan cleanup.
    db.execute(delete(EntityMention).where(EntityMention.entity_id == eid))
    db.commit()
    removed = EntityRepository(db).delete_orphans(ctx["user_id"])
    assert eid in removed
    assert EntityRepository(db).get(eid) is None


def test_extract_document_persists_entities_and_relationships(db, index, ctx, monkeypatch):
    # Fake extractor returns a fixed graph for any chunk.
    class FakeExtractor:
        def extract(self, text_):
            return Extraction(
                entities=[
                    ExEntity(name="NASA", type="ORGANIZATION", description="space agency"),
                    ExEntity(name="Apollo", type="EVENT", description="program"),
                ],
                relationships=[
                    ExRel(source="NASA", target="Apollo", type="runs",
                          evidence="NASA ran Apollo", confidence=0.9),
                ],
            )

    import diris.services.extraction as extraction_service

    monkeypatch.setattr(extraction_service, "get_extractor", lambda: FakeExtractor())
    monkeypatch.setattr(extraction_service, "get_entity_index", lambda: index)

    counts = extraction_service.extract_document(db, ctx["document_id"])
    assert counts["entities"] == 2
    assert counts["relationships"] == 1

    entities = EntityRepository(db).for_document(ctx["document_id"], ctx["user_id"])
    names = {e.canonical_name for e in entities}
    assert {"NASA", "Apollo"} <= names

    rels = RelationshipRepository(db).for_user(ctx["user_id"])
    assert len(rels) == 1
    assert rels[0].type == "runs"
