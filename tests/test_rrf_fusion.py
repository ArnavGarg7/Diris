"""Offline unit tests for Reciprocal Rank Fusion (no DB/services)."""
from diris.services.retrieval import rrf_fuse


def test_item_in_both_lists_ranks_highest():
    ranked, scores, sources = rrf_fuse({"vector": [1, 2, 3], "keyword": [2, 3, 4]})
    assert ranked[0] == 2  # rank1 in vector + rank0 in keyword -> best combined
    assert sources[2] == {"vector", "keyword"}
    assert scores[2] > scores[1]


def test_single_list_preserves_order():
    ranked, _, sources = rrf_fuse({"vector": [5, 6, 7]})
    assert ranked == [5, 6, 7]
    assert sources[5] == {"vector"}


def test_empty_lists():
    ranked, scores, sources = rrf_fuse({"vector": [], "keyword": []})
    assert ranked == []
    assert scores == {}
