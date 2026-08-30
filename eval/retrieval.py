"""Retrieval evaluation: recall@k and MRR over the labeled dataset.

Deterministic (local embeddings, no LLM). Seeds the labeled chunks, runs
hybrid_search per query, and scores whether/where the gold chunk is retrieved.

Run standalone:  python -m eval.retrieval
"""
from __future__ import annotations

from sqlalchemy import delete, text

from diris.db.models import User
from diris.db.repositories import ChunkRepository, DocumentRepository, UserRepository
from diris.db.session import SessionLocal
from diris.security import hash_password
from diris.services.retrieval import hybrid_search
from diris.vectorstore import get_vector_store

from .dataset import CHUNKS, QUERIES

_EVAL_EMAIL = "eval@diris.local"


def recall_at_k(ranked: list[int], gold: int, k: int) -> float:
    return 1.0 if gold in ranked[:k] else 0.0


def reciprocal_rank(ranked: list[int], gold: int) -> float:
    for i, cid in enumerate(ranked):
        if cid == gold:
            return 1.0 / (i + 1)
    return 0.0


def evaluate(db, top_k: int = 5) -> dict:
    """Seed the labeled data, evaluate retrieval, clean up. Uses whatever vector
    store is currently configured (caller should set a scratch one)."""
    _cleanup(db)
    user = UserRepository(db).create(_EVAL_EMAIL, hash_password("evalpass123"))
    doc = DocumentRepository(db).create(
        user_id=user.id, original_filename="eval.txt", stored_path="/eval",
        content_type="text/plain", size_bytes=1,
    )
    chunks = ChunkRepository(db).add_chunks(doc.id, CHUNKS)
    gold_ids = [c.id for c in chunks]  # dataset index -> chunk id

    # Force FULLTEXT sync so the keyword retriever sees the new rows.
    db.execute(text("OPTIMIZE TABLE chunks"))
    db.commit()

    vector_store = get_vector_store()
    vector_store.upsert(
        ids=[str(c.id) for c in chunks],
        texts=[c.content for c in chunks],
        metadatas=[{"user_id": user.id, "document_id": doc.id, "chunk_index": c.chunk_index} for c in chunks],
    )

    recalls, rrs = [], []
    for query, gold_idx in QUERIES:
        ranked = [r.chunk_id for r in hybrid_search(db, user, query, top_k=top_k)]
        gold = gold_ids[gold_idx]
        recalls.append(recall_at_k(ranked, gold, top_k))
        rrs.append(reciprocal_rank(ranked, gold))

    metrics = {
        "n": len(QUERIES),
        "top_k": top_k,
        f"recall@{top_k}": round(sum(recalls) / len(recalls), 3),
        "mrr": round(sum(rrs) / len(rrs), 3),
    }
    _cleanup(db)
    return metrics


def _cleanup(db) -> None:
    db.rollback()
    for uid in db.execute(
        User.__table__.select().where(User.email == _EVAL_EMAIL)
    ).fetchall():
        db.execute(delete(User).where(User.id == uid[0]))  # cascade removes chunks
    db.commit()


if __name__ == "__main__":  # pragma: no cover
    import tempfile

    from diris.vectorstore import set_entity_index, set_vector_store
    from diris.vectorstore.chroma_store import ChromaVectorStore

    tmp = tempfile.mkdtemp()
    set_vector_store(ChromaVectorStore(persist_dir=tmp + "/c", collection_name="eval_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=tmp + "/e", collection_name="eval_entities"))
    with SessionLocal() as session:
        print(evaluate(session))
