"""Integration tests for chunk + processing-status repositories (real MySQL).

Skipped if MySQL isn't reachable. These are repository-level (no HTTP), so they
create a user + document row directly.
"""
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from diris.db import models  # noqa: F401
from diris.db.models import (
    Chunk,
    Document,
    DocumentMetadata,
    DocumentProcessingStatus,
    User,
)
from diris.db.repositories import (
    ChunkRepository,
    DocumentRepository,
    ProcessingStatusRepository,
    UserRepository,
)
from diris.db.session import Base, SessionLocal, engine
from diris.security import hash_password


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="MySQL not reachable — start it with `docker compose up -d`",
)


def _wipe(db) -> None:
    db.execute(delete(Chunk))
    db.execute(delete(DocumentProcessingStatus))
    db.execute(delete(DocumentMetadata))
    db.execute(delete(Document))
    db.execute(delete(User))
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
def document(db):
    user = UserRepository(db).create("chunk@x.com", hash_password("secret123"))
    return DocumentRepository(db).create(
        user_id=user.id,
        original_filename="doc.txt",
        stored_path="/fake/path/doc.txt",  # repo doesn't touch disk
        content_type="text/plain",
        size_bytes=42,
    )


def test_add_and_list_chunks_preserves_order(db, document):
    texts = ["first chunk", "second chunk", "third chunk"]
    ChunkRepository(db).add_chunks(document.id, texts)

    listed = ChunkRepository(db).list_for_document(document.id)
    assert [c.chunk_index for c in listed] == [0, 1, 2]
    assert [c.content for c in listed] == texts
    assert listed[0].char_count == len("first chunk")


def test_duplicate_chunk_index_violates_unique_constraint(db, document):
    db.add(Chunk(document_id=document.id, chunk_index=0, content="a", char_count=1))
    db.add(Chunk(document_id=document.id, chunk_index=0, content="b", char_count=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_deleting_document_cascades_to_chunks(db, document):
    ChunkRepository(db).add_chunks(document.id, ["x", "y"])
    # DB-level ON DELETE CASCADE removes the chunks.
    db.execute(delete(Document).where(Document.id == document.id))
    db.commit()
    remaining = db.execute(
        select(Chunk).where(Chunk.document_id == document.id)
    ).scalars().all()
    assert remaining == []


def test_processing_status_updates_current_and_appends_history(db, document):
    repo = ProcessingStatusRepository(db)
    repo.record(document.id, "processing", stage="extract")
    repo.record(document.id, "done", stage="chunk")

    db.refresh(document)
    assert document.status == "done"  # denormalized current state updated

    history = repo.history_for_document(document.id)
    assert [h.status for h in history] == ["processing", "done"]
    assert history[0].stage == "extract"
