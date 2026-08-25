"""Authentication routes: register and login."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...security import create_access_token
from ...services import users as user_service
from ..schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    return user_service.register_user(db, payload.email, payload.password)


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    # OAuth2 form uses `username`; we treat it as the email.
    user = user_service.authenticate_user(db, form.username, form.password)
    return Token(access_token=create_access_token(subject=user.email))
