"""Integration tests for the auth API against a REAL MySQL.

If MySQL isn't reachable (e.g. you haven't run `docker compose up -d`), the whole
module is skipped so the offline suite stays green. No SQLite fallback — we test
against the same engine we ship.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from diris.api.main import app
from diris.db import models  # noqa: F401  (register model on metadata)
from diris.db.session import Base, engine


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


@pytest.fixture(autouse=True)
def clean_users_table():
    """Ensure the table exists and start each test from an empty users table."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    yield
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))


def test_register_login_me_happy_path():
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "a@b.com"
    assert "id" in body
    assert "hashed_password" not in body  # never leak the hash

    r = client.post("/auth/login", data={"username": "a@b.com", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


def test_duplicate_email_rejected():
    payload = {"email": "dup@b.com", "password": "secret123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_me_requires_authentication():
    assert client.get("/me").status_code == 401


def test_login_wrong_password_rejected():
    client.post("/auth/register", json={"email": "c@d.com", "password": "secret123"})
    r = client.post("/auth/login", data={"username": "c@d.com", "password": "nope"})
    assert r.status_code == 401


def test_registration_input_validation():
    assert client.post(
        "/auth/register", json={"email": "x@y.com", "password": "short"}
    ).status_code == 422  # password too short
    assert client.post(
        "/auth/register", json={"email": "notanemail", "password": "secret123"}
    ).status_code == 422  # invalid email
