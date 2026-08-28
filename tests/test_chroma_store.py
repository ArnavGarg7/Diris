"""Unit tests for ChromaVectorStore (isolated temp dir; no MySQL needed).

Skipped if chromadb can't be imported/initialized.
"""
import pytest

try:
    import chromadb  # noqa: F401

    _CHROMA_OK = True
except Exception:  # pragma: no cover
    _CHROMA_OK = False

pytestmark = pytest.mark.skipif(not _CHROMA_OK, reason="chromadb not available")


def _make_store(tmp_path):
    from diris.vectorstore.chroma_store import ChromaVectorStore

    return ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma"), collection_name="test_chunks"
    )


def test_query_matches_paraphrase_not_keywords(tmp_path):
    vs = _make_store(tmp_path)
    vs.upsert(
        ids=["1", "2"],
        texts=[
            "Neil Armstrong walked on the Moon in 1969.",
            "Photosynthesis happens in the leaves of plants.",
        ],
        metadatas=[{"user_id": 1, "document_id": 10}, {"user_id": 1, "document_id": 10}],
    )
    # No shared keywords with chunk 1 — dense embeddings still match it.
    res = vs.query("who stepped onto the lunar surface", top_k=1, where={"user_id": 1})
    assert res
    assert res[0].chunk_id == 1
    assert res[0].score > 0  # cosine similarity


def test_metadata_filter_isolates_users(tmp_path):
    vs = _make_store(tmp_path)
    vs.upsert(ids=["1"], texts=["alice private note"], metadatas=[{"user_id": 1, "document_id": 10}])
    vs.upsert(ids=["2"], texts=["bob private note"], metadatas=[{"user_id": 2, "document_id": 20}])
    res = vs.query("private note", top_k=5, where={"user_id": 1})
    assert {m.chunk_id for m in res} == {1}


def test_delete_document_removes_its_vectors(tmp_path):
    vs = _make_store(tmp_path)
    vs.upsert(
        ids=["1", "2"],
        texts=["a", "b"],
        metadatas=[{"user_id": 1, "document_id": 10}, {"user_id": 1, "document_id": 10}],
    )
    assert vs.count() == 2
    vs.delete_document(10)
    assert vs.count() == 0
