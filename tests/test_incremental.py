"""Incremental update (M13): chunk-level diff on re-processing.
Real MySQL + temp Chroma + counting fake extractor + no-op graph. Skipped if
MySQL isn't reachable."""
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
from diris.extraction import set_extractor
from diris.extraction.schema import Entity as ExEntity
from diris.extraction.schema import Extraction
from diris.graph import set_graph_store
from diris.graph.base import GraphStore
from diris.security import hash_password
from diris.services.processing import process_document
from diris.vectorstore import set_entity_index, set_vector_store


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="MySQL not reachable")


class CountingExtractor:
    def __init__(self):
        self.calls = 0

    def extract(self, text_: str) -> Extraction:
        self.calls += 1
        # Entity name stable per content, so resolution is deterministic.
        name = f"ent_{abs(hash(text_)) % 100000}"
        return Extraction(entities=[ExEntity(name=name, type="CONCEPT", description="")], relationships=[])


class NoOpGraphStore(GraphStore):
    def upsert_entity(self, *a, **k): ...
    def upsert_relationship(self, *a, **k): ...
    def delete_document_relationships(self, *a, **k): ...
    def delete_entities(self, *a, **k): ...
    def neighborhood(self, *a, **k): return None
    def full_graph(self, *a, **k): return {"nodes": [], "edges": []}
    def shortest_path(self, *a, **k): return {"nodes": [], "edges": [], "found": False}
    def clear(self): ...
    def close(self): ...


def _wipe(db) -> None:
    for model in (Relationship, EntityMention, EntityAlias, Entity, Chunk,
                  DocumentMetadata, Document, User):
        db.execute(delete(model))
    db.commit()


@pytest.fixture
def env(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    set_vector_store(ChromaVectorStore(persist_dir=str(tmp_path / "chunks"), collection_name="test_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=str(tmp_path / "entities"), collection_name="test_entities"))
    set_graph_store(NoOpGraphStore())
    extractor = CountingExtractor()
    set_extractor(extractor)

    Base.metadata.create_all(engine)
    db = SessionLocal()
    _wipe(db)
    yield {"db": db, "tmp": tmp_path, "extractor": extractor}
    _wipe(db)
    db.close()
    set_vector_store(None)
    set_entity_index(None)
    set_graph_store(None)


# Two paragraphs long enough to become two separate chunks (~900 chars each).
_APPLES = "Apples are red and sweet. " * 40
_BANANAS = "Bananas are yellow and soft. " * 35
_CHERRIES = "Cherries are small and tart. " * 35


def _make_doc(db, tmp_path, body: str) -> int:
    path = tmp_path / "doc.txt"
    path.write_text(body, encoding="utf-8")
    user = db.execute(models.User.__table__.select()).first()
    if user is None:
        user_obj = UserRepository(db).create("inc@x.com", hash_password("secret123"))
        uid = user_obj.id
    else:
        uid = user[0]
    doc = DocumentRepository(db).create(
        user_id=uid, original_filename="doc.txt", stored_path=str(path),
        content_type="text/plain", size_bytes=len(body.encode()),
    )
    return doc.id


def _chunks(db, doc_id):
    # End the current read transaction so we see the worker session's commits
    # (MySQL InnoDB default isolation is REPEATABLE READ).
    db.rollback()
    return ChunkRepository(db).list_for_document(doc_id)


def test_incremental_reuse_add_remove(env):
    db, tmp, extractor = env["db"], env["tmp"], env["extractor"]

    doc_id = _make_doc(db, tmp, f"{_APPLES}\n\n{_BANANAS}")
    process_document(doc_id)
    c1 = _chunks(db, doc_id)
    assert len(c1) == 2
    assert extractor.calls == 2  # both chunks extracted initially
    apple_id = next(c.id for c in c1 if "Apples" in c.content)
    banana_id = next(c.id for c in c1 if "Bananas" in c.content)

    # --- reprocess UNCHANGED -> skip, no new extraction ---
    process_document(doc_id)
    c2 = _chunks(db, doc_id)
    assert {c.id for c in c2} == {apple_id, banana_id}  # same chunk rows
    assert extractor.calls == 2  # extraction NOT re-run

    # --- change: keep apples, replace bananas with cherries ---
    (tmp / "doc.txt").write_text(f"{_APPLES}\n\n{_CHERRIES}", encoding="utf-8")
    process_document(doc_id)
    c3 = _chunks(db, doc_id)
    ids3 = {c.id for c in c3}
    assert len(c3) == 2
    assert apple_id in ids3            # apples chunk REUSED (same id)
    assert banana_id not in ids3       # bananas chunk REMOVED
    assert any("Cherries" in c.content for c in c3)  # cherries ADDED
    assert extractor.calls == 3        # only the ONE new chunk was extracted


def test_deleting_document_removes_orphan_entities(env):
    """Deleting a document must not leave its entities behind as orphans."""
    from sqlalchemy import func, select

    from diris.services.documents import delete_document

    db, tmp = env["db"], env["tmp"]
    doc_id = _make_doc(db, tmp, f"{_APPLES}\n\n{_BANANAS}")
    process_document(doc_id)
    db.rollback()  # see the worker session's commits

    # extraction produced entities (each with a mention on this document)
    assert db.execute(select(func.count()).select_from(Entity)).scalar() > 0

    doc = db.get(Document, doc_id)
    user = db.get(User, doc.user_id)
    delete_document(db, user, doc_id)
    db.rollback()

    assert db.get(Document, doc_id) is None  # document gone...
    # ...and no entities left orphaned (all belonged to that one document)
    assert db.execute(select(func.count()).select_from(Entity)).scalar() == 0
