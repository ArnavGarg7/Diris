"""Integration tests for the document library against real MySQL.

Skipped entirely if MySQL isn't reachable (run `docker compose up -d`).
Cleans up both DB rows and any files written to the upload dir.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from diris.api.main import app
from diris.db import models  # noqa: F401
from diris.db.models import Document, DocumentMetadata, User
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
    """Delete all documents/users, and unlink the files those documents point to."""
    with SessionLocal() as db:
        for doc in db.execute(select(Document)).scalars():
            Path(doc.stored_path).unlink(missing_ok=True)
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


def _token(email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post("/auth/login", data={"username": email, "password": "secret123"})
    return r.json()["access_token"]


def _auth(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(email)}"}


def test_upload_list_get_delete_flow():
    headers = _auth("owner@x.com")
    files = {"file": ("notes.txt", b"hello world contents", "text/plain")}

    r = client.post("/documents", files=files, headers=headers)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["original_filename"] == "notes.txt"
    assert doc["size_bytes"] == len(b"hello world contents")
    assert doc["status"] == "uploaded"
    assert "stored_path" not in doc  # internal path never exposed
    doc_id = doc["id"]

    assert len(client.get("/documents", headers=headers).json()) == 1
    assert client.get(f"/documents/{doc_id}", headers=headers).status_code == 200

    assert client.delete(f"/documents/{doc_id}", headers=headers).status_code == 204
    assert client.get("/documents", headers=headers).json() == []
    assert client.get(f"/documents/{doc_id}", headers=headers).status_code == 404


def test_upload_rejects_unsupported_extension():
    headers = _auth("owner@x.com")
    files = {"file": ("evil.exe", b"MZ...", "application/octet-stream")}
    assert client.post("/documents", files=files, headers=headers).status_code == 400


def test_requires_authentication():
    files = {"file": ("notes.txt", b"data", "text/plain")}
    assert client.post("/documents", files=files).status_code == 401
    assert client.get("/documents").status_code == 401


def test_users_are_isolated():
    a_headers = _auth("alice@x.com")
    b_headers = _auth("bob@x.com")

    files = {"file": ("alice.txt", b"secret", "text/plain")}
    a_doc_id = client.post("/documents", files=files, headers=a_headers).json()["id"]

    # Bob sees nothing, and cannot fetch or delete Alice's document (404, not 403).
    assert client.get("/documents", headers=b_headers).json() == []
    assert client.get(f"/documents/{a_doc_id}", headers=b_headers).status_code == 404
    assert client.delete(f"/documents/{a_doc_id}", headers=b_headers).status_code == 404
    # Alice still has it.
    assert client.get(f"/documents/{a_doc_id}", headers=a_headers).status_code == 200
