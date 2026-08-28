from .base import VectorMatch, VectorStoreBase
from .provider import (
    get_entity_index,
    get_vector_store,
    set_entity_index,
    set_vector_store,
)
from .store import Chunk, VectorStore  # legacy TF-IDF reference impl (old MVP pipeline)

__all__ = [
    "VectorStore",       # legacy TF-IDF
    "Chunk",
    "VectorStoreBase",   # M5 interface
    "VectorMatch",
    "get_vector_store",
    "set_vector_store",
    "get_entity_index",
    "set_entity_index",
]
