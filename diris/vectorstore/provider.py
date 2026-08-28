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


# A SECOND collection, holding entity-NAME embeddings, used for entity
# resolution in M6 (kept separate from the chunk embeddings above).
_entity_index: VectorStoreBase | None = None


def get_entity_index() -> VectorStoreBase:
    global _entity_index
    if _entity_index is None:
        from ..config import settings
        from .chroma_store import ChromaVectorStore

        _entity_index = ChromaVectorStore(collection_name=settings.chroma_entity_collection)
    return _entity_index


def set_entity_index(store: VectorStoreBase | None) -> None:
    global _entity_index
    _entity_index = store
