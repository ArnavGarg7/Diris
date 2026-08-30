"""Conversation endpoints (M12). User-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.repositories import ConversationRepository
from ...db.session import get_db
from ..deps import get_current_user
from ..schemas import ConversationDetailOut, ConversationOut, MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationOut:
    conv = ConversationRepository(db).create(current_user.id)
    return ConversationOut.from_conversation(conv)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationOut]:
    convs = ConversationRepository(db).list_for_user(current_user.id)
    return [ConversationOut.from_conversation(c) for c in convs]


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailOut:
    repo = ConversationRepository(db)
    conv = repo.get_for_user(conversation_id, current_user.id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    messages = repo.messages(conv.id)
    return ConversationDetailOut(
        id=conv.id,
        created_at=conv.created_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )
