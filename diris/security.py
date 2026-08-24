"""Framework-agnostic security primitives: password hashing + JWT.

Kept out of the `api/` layer on purpose so the service layer can hash/verify
passwords and mint tokens without importing FastAPI. The FastAPI-specific
`get_current_user` dependency lives in `api/deps.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """One-way argon2 hash (includes a random salt). We never store plaintext."""
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/unknown hash -> treat as a failed auth, never raise to the caller.
        return False


def create_access_token(subject: str) -> str:
    """Sign a JWT whose `sub` claim identifies the user (we use the email)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Return the JWT payload if the signature and expiry are valid, else None."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
