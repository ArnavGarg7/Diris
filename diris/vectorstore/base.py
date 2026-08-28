"""Interface for a dense vector store (the M5 abstraction).

The concrete backend is ChromaDB (see chroma_store.py). Keeping this interface
thin means the storage/query code above it never depends on Chroma specifics, so
a future swap (a hosted vector DB, a different embedder) stays local.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VectorMatch:
    chunk_id: int
    document_id: int | None
    score: float          # higher = more similar (cosine similarity)
    text: str
    metadata: dict


class VectorStoreBase(ABC):
    @abstractmethod
    def upsert(
        self, ids: list[str], texts: list[str], metadatas: list[dict]
    ) -> None:
        """Insert-or-update vectors. `ids` are stringified MySQL chunk ids."""

    @abstractmethod
    def query(
        self, text: str, top_k: int, where: dict | None = None
    ) -> list[VectorMatch]:
        """Return the top_k most similar chunks, optionally metadata-filtered."""

    @abstractmethod
    def delete_document(self, document_id: int) -> None:
        """Remove all vectors belonging to a document (idempotent reprocessing)."""

    @abstractmethod
    def count(self) -> int:
        """Total number of vectors stored."""
