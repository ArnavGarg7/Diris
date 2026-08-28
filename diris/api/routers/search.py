"""Semantic search endpoint (M5). Vector-only; user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...db.models import User
from ...services.search import semantic_search
from ..deps import get_current_user
from ..schemas import SearchResultOut

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResultOut])
def search(
    q: str = Query(..., min_length=1, description="natural-language query"),
    top_k: int = Query(6, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> list[SearchResultOut]:
    matches = semantic_search(current_user, q, top_k=top_k)
    return [
        SearchResultOut(
            chunk_id=m.chunk_id,
            document_id=m.document_id,
            score=m.score,
            content=m.text,
        )
        for m in matches
    ]
