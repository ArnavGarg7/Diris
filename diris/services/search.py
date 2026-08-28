"""Semantic search over a user's chunks (M5 vector-only building block).

This is intentionally vector-only. M8 will fuse this with keyword + graph
retrieval and ranking; here we just expose dense similarity search, scoped to
the caller via a metadata filter.
"""
from __future__ import annotations

from ..db.models import User
from ..vectorstore import VectorMatch, get_vector_store


def semantic_search(user: User, query: str, top_k: int = 6) -> list[VectorMatch]:
    if not query.strip():
        return []
    # where filter enforces per-user isolation at the vector layer.
    return get_vector_store().query(query, top_k=top_k, where={"user_id": user.id})
