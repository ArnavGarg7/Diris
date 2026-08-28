"""Integration test: upload -> processing embeds -> semantic search finds it.

Needs live MySQL (skipped otherwise). Injects a temp-dir Chroma store so it never
touches the real data/chroma.
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
    DocumentProcessingStatus,
    User,
)
from diris.db.session import Base, SessionLocal, engine
from diris.vectorstore import set_vector_store


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

client = TestClient(app)


def _wipe() -> None:
    with SessionLocal() as db:
        for doc in db.execute(select(Document)).scalars():
            Path(doc.stored_path).unlink(missing_ok=True)
        db.execute(delete(Chunk))
        db.execute(delete(DocumentProcessingStatus))
        db.execute(delete(DocumentMetadata))
        db.execute(delete(Document))
        db.execute(delete(User))
        db.commit()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    # Inject a throwaway vector store so tests never pollute data/chroma.
    set_vector_store(
        ChromaVectorStore(persist_dir=str(tmp_path / "chroma"), collection_name="test_chunks")
    )
    Base.metadata.create_all(engine)
    _wipe()
    yield
    _wipe()
    set_vector_store(None)  # reset to the real store


def _auth(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_search_finds_semantically_relevant_chunk():
    headers = _auth("s@x.com")
    body = b"Neil Armstrong walked on the Moon in 1969 during the Apollo 11 mission."
    r = client.post("/documents", files={"file": ("moon.txt", body, "text/plain")}, headers=headers)
    doc_id = r.json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"

    res = client.get(
        "/search", params={"q": "who stepped onto the lunar surface"}, headers=headers
    )
    assert res.status_code == 200
    results = res.json()
    assert results
    assert results[0]["document_id"] == doc_id
    assert results[0]["score"] > 0
    assert "Moon" in results[0]["content"]


def test_search_is_user_scoped():
    a = _auth("alice@x.com")
    b = _auth("bob@x.com")
    client.post(
        "/documents",
        files={"file": ("a.txt", b"Alice notes about quantum physics.", "text/plain")},
        headers=a,
    )
    # Bob's library is empty -> no results even for a matching query.
    res = client.get("/search", params={"q": "quantum physics"}, headers=b)
    assert res.status_code == 200
    assert res.json() == []


def test_search_requires_auth():
    assert client.get("/search", params={"q": "anything"}).status_code == 401
