"""FastAPI dependencies — notably `get_current_user`, the auth gate.

Flow: read the Bearer token -> verify signature/expiry -> load the user from DB.
Any failure raises 401. Protected routes just declare
`current: User = Depends(get_current_user)`.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..db.models import User
from ..db.repositories import UserRepository
from ..db.session import get_db
from ..security import decode_token

# tokenUrl points Swagger's "Authorize" button at our login endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    email = payload.get("sub")
    if not email:
        raise credentials_exception
    user = UserRepository(db).get_by_email(email)
    if user is None:
        raise credentials_exception
    return user
