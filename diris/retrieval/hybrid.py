"""Hybrid retrieval (FR-7): fuse vector, graph, and keyword evidence.

Given a query we gather three signals and merge them into one evidence
bundle that the QA layer turns into a cited answer:

  1. Vector   — top-k TF-IDF chunks most similar to the query.
  2. Graph    — entities in the query matched against KG nodes, then their
                neighborhood of relationships (this is the cross-document
                reasoning signal that plain RAG lacks).
  3. Keyword  — chunks that provenance-link the matched graph facts, ensuring
                every graph edge we cite has its source text available.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import settings
from ..graph import KnowledgeGraph
from ..vectorstore import Chunk, VectorStore


@dataclass
class Evidence:
    chunks: list[tuple[Chunk, float]] = field(default_factory=list)  # (chunk, score)
    graph_nodes: dict = field(default_factory=dict)
    graph_edges: list[dict] = field(default_factory=list)
    matched_entities: list[str] = field(default_factory=list)


def retrieve(
    query: str,
    vs: VectorStore,
    kg: KnowledgeGraph,
    top_k: int | None = None,
    hops: int | None = None,
) -> Evidence:
    top_k = top_k or settings.vector_top_k
    hops = hops if hops is not None else settings.graph_hops

    # 1. Vector search
    vector_hits = vs.search(query, top_k=top_k)
    chunk_by_id: dict[str, tuple[Chunk, float]] = {c.id: (c, s) for c, s in vector_hits}

    # 2. Graph: find entities named in the query, pull their neighborhood
    matched = kg.find_entities(query)
    sub = kg.neighborhood(matched, hops=hops) if matched else {"nodes": {}, "edges": []}

    # 3. Keyword/provenance: add chunks that support the graph facts we found
    provenance_ids: set[str] = set()
    for node in sub["nodes"].values():
        provenance_ids.update(node.get("mentions", []))
    for edge in sub["edges"]:
        provenance_ids.update(edge.get("provenance", []))

    for cid in provenance_ids:
        if cid not in chunk_by_id:
            chunk = vs.get(cid)
            if chunk:
                chunk_by_id[cid] = (chunk, 0.0)  # graph-sourced, no vector score

    # Rank: vector-scored chunks first, then graph-only provenance chunks.
    ranked = sorted(chunk_by_id.values(), key=lambda x: x[1], reverse=True)

    return Evidence(
        chunks=ranked,
        graph_nodes=sub["nodes"],
        graph_edges=sub["edges"],
        matched_entities=[sub["nodes"][m]["name"] for m in matched if m in sub["nodes"]],
    )
