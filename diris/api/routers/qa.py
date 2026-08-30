"""Question-answering endpoint (M9-M12): grounded, cited, multilingual answers,
optionally within a conversation (multi-turn memory)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.repositories import ConversationRepository
from ...db.session import get_db
from ...services.conversation import ask_in_conversation
from ...services.qa import answer_question
from ..deps import get_current_user
from ..schemas import AnswerOut, AskRequest, CitationOut

router = APIRouter(tags=["qa"])


@router.post("/ask", response_model=AnswerOut)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnswerOut:
    conversation_id = None
    if payload.conversation_id is not None:
        conv = ConversationRepository(db).get_for_user(payload.conversation_id, current_user.id)
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        result = ask_in_conversation(
            db, current_user, conv, payload.question, answer_language=payload.answer_language
        )
        conversation_id = conv.id
    else:
        result = answer_question(
            db, current_user, payload.question, answer_language=payload.answer_language
        )

    return AnswerOut(
        answer=result.answer,
        answered=result.answered,
        confidence=result.confidence,
        citations=[
            CitationOut(
                chunk_id=c.chunk_id, document_id=c.document_id,
                document_name=c.document_name, section=c.section,
                chunk_index=c.chunk_index, snippet=c.snippet,
            )
            for c in result.citations
        ],
        reasoning=result.reasoning,
        conversation_id=conversation_id,
    )
