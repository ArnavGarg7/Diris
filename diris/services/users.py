"""User-related business logic: registration and authentication.

Raises HTTPException for expected failure cases so routes stay thin. (This is a
pragmatic coupling to Starlette's exception type; if we ever reuse services
outside HTTP we'd translate these to domain errors.)
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..db.models import User
from ..db.repositories import UserRepository
from ..security import hash_password, verify_password


def register_user(db: Session, email: str, password: str) -> User:
    repo = UserRepository(db)
    if repo.get_by_email(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return repo.create(email=email, hashed_password=hash_password(password))


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = UserRepository(db).get_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return user
