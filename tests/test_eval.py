"""Evaluation gate: retrieval recall@k / MRR must stay above thresholds.
Deterministic (local embeddings, no LLM). Skipped if MySQL isn't reachable."""
import pytest
from sqlalchemy import text

from diris.db.session import SessionLocal, engine
from diris.vectorstore import set_entity_index, set_vector_store
from eval.retrieval import evaluate


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="MySQL not reachable")


def test_retrieval_meets_quality_thresholds(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    set_vector_store(ChromaVectorStore(persist_dir=str(tmp_path / "c"), collection_name="eval_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=str(tmp_path / "e"), collection_name="eval_entities"))
    try:
        with SessionLocal() as db:
            metrics = evaluate(db, top_k=5)
    finally:
        set_vector_store(None)
        set_entity_index(None)

    # On the labeled paraphrase set, hybrid retrieval should nearly always find
    # the gold chunk in the top 5, and rank it high.
    assert metrics["recall@5"] >= 0.8, metrics
    assert metrics["mrr"] >= 0.6, metrics
