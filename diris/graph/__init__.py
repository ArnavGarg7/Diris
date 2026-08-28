from .base import GraphStore
from .provider import get_graph_store, set_graph_store
from .store import KnowledgeGraph  # legacy pure-Python reference impl

__all__ = [
    "KnowledgeGraph",   # legacy reference
    "GraphStore",       # M7 interface
    "get_graph_store",
    "set_graph_store",
]
