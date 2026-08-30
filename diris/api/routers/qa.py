"""Question-answering endpoint (M9): grounded, cited answers over the user's docs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.session import get_db
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
    result = answer_question(db, current_user, payload.question)
    return AnswerOut(
        answer=result.answer,
        answered=result.answered,
        confidence=result.confidence,
        citations=[
            CitationOut(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_name=c.document_name,
                section=c.section,
                chunk_index=c.chunk_index,
                snippet=c.snippet,
            )
            for c in result.citations
        ],
        reasoning=result.reasoning,
    )
