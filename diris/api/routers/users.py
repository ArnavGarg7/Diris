"""User routes. `/me` is our first protected endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...db.models import User
from ..deps import get_current_user
from ..schemas import UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user
