"""Process-wide accessor for the graph store (test-injectable)."""
from __future__ import annotations

from .base import GraphStore

_store: GraphStore | None = None


def get_graph_store() -> GraphStore:
    global _store
    if _store is None:
        from .neo4j_store import Neo4jGraphStore  # lazy: connects to Neo4j

        _store = Neo4jGraphStore()
    return _store


def set_graph_store(store: GraphStore | None) -> None:
    global _store
    _store = store
