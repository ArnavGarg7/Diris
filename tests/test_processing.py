"""Integration tests for the M4 processing pipeline (real MySQL + real files).

With Starlette's TestClient, background tasks run before the client call returns,
so processing is complete by the time `client.post(...)` returns.
Skipped if MySQL isn't reachable.
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
def clean_db():
    Base.metadata.create_all(engine)
    _wipe()
    yield
    _wipe()


def _auth(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(headers, name, content, ctype="text/plain"):
    return client.post("/documents", files={"file": (name, content, ctype)}, headers=headers)


def test_upload_processes_to_done_with_chunks():
    headers = _auth("proc@x.com")
    body = b"First paragraph about the Moon.\n\nSecond paragraph about Mars."
    r = _upload(headers, "notes.txt", body)
    assert r.status_code == 201
    assert r.json()["status"] == "uploaded"  # response captured pre-processing state
    doc_id = r.json()["id"]

    # Background task has run by now -> status advanced to done.
    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "done"

    chunks = client.get(f"/documents/{doc_id}/chunks", headers=headers).json()
    assert len(chunks) >= 1
    assert chunks[0]["chunk_index"] == 0
    assert all(c["char_count"] == len(c["content"]) for c in chunks)

    history = client.get(f"/documents/{doc_id}/status", headers=headers).json()
    statuses = [h["status"] for h in history]
    assert statuses[0] == "processing"
    assert statuses[-1] == "done"


def test_bad_file_marks_failed_without_crashing():
    headers = _auth("proc@x.com")
    # A .pdf that isn't a real PDF: passes upload validation, fails extraction.
    r = _upload(headers, "broken.pdf", b"this is not a real pdf", "application/pdf")
    assert r.status_code == 201
    doc_id = r.json()["id"]

    assert client.get(f"/documents/{doc_id}", headers=headers).json()["status"] == "failed"
    history = client.get(f"/documents/{doc_id}/status", headers=headers).json()
    assert history[-1]["status"] == "failed"
    assert history[-1]["message"]  # error message recorded


def test_reprocess_is_idempotent():
    headers = _auth("proc@x.com")
    r = _upload(headers, "notes.txt", b"Some text.\n\nMore text here.")
    doc_id = r.json()["id"]
    n1 = len(client.get(f"/documents/{doc_id}/chunks", headers=headers).json())
    assert n1 >= 1

    assert client.post(f"/documents/{doc_id}/reprocess", headers=headers).status_code == 200
    n2 = len(client.get(f"/documents/{doc_id}/chunks", headers=headers).json())
    assert n2 == n1  # not doubled


def test_reprocess_requires_ownership():
    a = _auth("alice@x.com")
    b = _auth("bob@x.com")
    doc_id = _upload(a, "a.txt", b"alice data").json()["id"]
    assert client.post(f"/documents/{doc_id}/reprocess", headers=b).status_code == 404
    assert client.get(f"/documents/{doc_id}/chunks", headers=b).status_code == 404
