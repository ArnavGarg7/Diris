"""GraphStore interface (M7). The concrete backend is Neo4j; the pure-Python
KnowledgeGraph in store.py remains as a reference implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod


class GraphStore(ABC):
    @abstractmethod
    def upsert_entity(self, entity_id: int, user_id: int, name: str, type: str) -> None:
        """Idempotently create/update an entity node."""

    @abstractmethod
    def upsert_relationship(
        self, *, rel_id: int, user_id: int, source_id: int, target_id: int,
        type: str, confidence: float, evidence: str | None,
        document_id: int, chunk_id: int,
    ) -> None:
        """Idempotently create/update an edge between two existing entity nodes."""

    @abstractmethod
    def delete_document_relationships(self, document_id: int) -> None:
        """Remove a document's edges (for idempotent re-projection)."""

    @abstractmethod
    def neighborhood(self, user_id: int, entity_id: int, hops: int = 1) -> dict | None:
        """Return {nodes, edges} within `hops` of an entity, or None if absent."""

    @abstractmethod
    def clear(self) -> None:
        """Delete everything (tests)."""

    @abstractmethod
    def close(self) -> None:
        ...
