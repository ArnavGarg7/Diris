"""Hybrid retrieval (M8): fuse dense vector, keyword, and graph retrieval.

Each retriever returns a *ranked list of chunk ids*. We combine them with
Reciprocal Rank Fusion (RRF) — fusing ranks, not scores, because the retrievers'
raw scores (cosine vs. BM25 vs. graph hops) aren't comparable. Every result
carries provenance (which retrievers found it).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db.models import Chunk, User
from ..db.repositories import ChunkRepository, EntityRepository
from ..graph import get_graph_store
from ..vectorstore import get_entity_index, get_vector_store

RRF_K = 60  # standard RRF constant; dampens the weight of low ranks


@dataclass
class HybridResult:
    chunk_id: int
    document_id: int | None
    content: str
    score: float
    sources: list[str]  # which retrievers contributed (vector/keyword/graph)


# -- sub-retrievers (each returns ranked chunk ids) ------------------------
def _vector_ids(user: User, query: str, top_k: int) -> list[int]:
    try:
        matches = get_vector_store().query(query, top_k=top_k, where={"user_id": user.id})
        return [m.chunk_id for m in matches]
    except Exception:  # noqa: BLE001  (a retriever hiccup must not break search)
        return []


def _keyword_ids(db, user: User, query: str, top_k: int) -> list[int]:
    try:
        return ChunkRepository(db).keyword_search(user.id, query, limit=top_k)
    except Exception:  # noqa: BLE001
        return []


def _graph_ids(db, user: User, query: str, top_k: int) -> list[int]:
    """Seed entities from the query (entity embedding index), expand one hop in
    Neo4j, then collect the chunks that mention those entities."""
    try:
        seeds = get_entity_index().query(query, top_k=3, where={"user_id": user.id})
    except Exception:  # noqa: BLE001
        return []
    seed_ids = [m.chunk_id for m in seeds]  # entity index keys by entity id
    if not seed_ids:
        return []

    entity_ids = set(seed_ids)
    try:
        graph = get_graph_store()
        for eid in seed_ids:
            sub = graph.neighborhood(user.id, eid, hops=1)
            if sub:
                entity_ids.update(n["entity_id"] for n in sub["nodes"])
    except Exception:  # noqa: BLE001  (Neo4j down -> just use the seeds)
        pass

    return EntityRepository(db).chunk_ids_for_entities(list(entity_ids), limit=top_k)


# -- fusion ----------------------------------------------------------------
def rrf_fuse(ranked_lists: dict[str, list[int]], k: int = RRF_K):
    """Return (ranked_ids, scores, sources). score(id) = sum 1/(k + rank+1)."""
    scores: dict[int, float] = {}
    sources: dict[int, set[str]] = {}
    for source, ids in ranked_lists.items():
        for rank, cid in enumerate(ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            sources.setdefault(cid, set()).add(source)
    ranked = sorted(scores, key=lambda c: scores[c], reverse=True)
    return ranked, scores, sources


# -- public API ------------------------------------------------------------
def hybrid_search(db, user: User, query: str, top_k: int = 6) -> list[HybridResult]:
    if not query.strip():
        return []
    lists = {
        "vector": _vector_ids(user, query, top_k),
        "keyword": _keyword_ids(db, user, query, top_k),
        "graph": _graph_ids(db, user, query, top_k),
    }
    ranked, scores, sources = rrf_fuse(lists)

    # Balance chunks across documents when multiple documents are retrieved,
    # ensuring comparative questions (e.g. "compare both books") get evidence from each.
    doc_to_cids: dict[int, list[int]] = {}
    for cid in ranked:
        chunk = db.get(Chunk, cid)
        if chunk is not None:
            doc_to_cids.setdefault(chunk.document_id, []).append(cid)

    selected_cids: list[int] = []
    if len(doc_to_cids) > 1 and top_k > 1:
        # Round-robin pick from each document up to top_k
        while len(selected_cids) < top_k and any(doc_to_cids.values()):
            for did in list(doc_to_cids.keys()):
                if doc_to_cids[did] and len(selected_cids) < top_k:
                    selected_cids.append(doc_to_cids[did].pop(0))
    else:
        selected_cids = ranked[:top_k]

    results: list[HybridResult] = []
    for cid in selected_cids:
        chunk = db.get(Chunk, cid)
        if chunk is None:
            continue
        results.append(
            HybridResult(
                chunk_id=cid,
                document_id=chunk.document_id,
                content=chunk.content,
                score=scores.get(cid, 0.0),
                sources=sorted(sources.get(cid, [])),
            )
        )
    return results
