"""Password hashing + JWT primitives. Offline — no DB or network."""
from diris.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"            # never stored in plaintext
    assert verify_password("secret123", h)
    assert not verify_password("wrong-password", h)


def test_hash_is_salted():
    # Same input hashes differently thanks to a random salt.
    assert hash_password("same") != hash_password("same")


def test_jwt_roundtrip():
    token = create_access_token("user@example.com")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user@example.com"


def test_decode_rejects_garbage():
    assert decode_token("not.a.jwt") is None


def test_verify_handles_malformed_hash():
    assert verify_password("whatever", "not-a-real-hash") is False
