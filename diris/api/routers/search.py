"""Semantic search endpoint (M5). Vector-only; user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.session import get_db
from ...services.retrieval import hybrid_search
from ...services.search import semantic_search
from ..deps import get_current_user
from ..schemas import HybridResultOut, SearchResultOut

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResultOut])
def search(
    q: str = Query(..., min_length=1, description="natural-language query"),
    top_k: int = Query(6, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> list[SearchResultOut]:
    """Vector-only semantic search (M5)."""
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


@router.get("/hybrid", response_model=list[HybridResultOut])
def hybrid(
    q: str = Query(..., min_length=1, description="natural-language query"),
    top_k: int = Query(6, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HybridResultOut]:
    """Hybrid retrieval (M8): dense vector + keyword + graph, fused with RRF."""
    results = hybrid_search(db, current_user, q, top_k=top_k)
    return [
        HybridResultOut(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            sources=r.sources,
        )
        for r in results
    ]
