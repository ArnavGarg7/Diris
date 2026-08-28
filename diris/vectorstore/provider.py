"""Process-wide accessor for the vector store.

Chroma's PersistentClient should be created once and reused. `set_vector_store`
lets tests inject a temp-dir store so they don't touch the real data/chroma.
"""
from __future__ import annotations

from .base import VectorStoreBase

_store: VectorStoreBase | None = None


def get_vector_store() -> VectorStoreBase:
    global _store
    if _store is None:
        from .chroma_store import ChromaVectorStore  # lazy: avoids importing chromadb at import time

        _store = ChromaVectorStore()
    return _store


def set_vector_store(store: VectorStoreBase | None) -> None:
    """Inject a store (tests) or reset to None to rebuild the default lazily."""
    global _store
    _store = store
