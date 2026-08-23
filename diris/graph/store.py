"""A minimal, dependency-free knowledge graph with JSON persistence.

Design goals (mapping to the PRD):
  * FR-6 merge duplicate entities, preserve provenance, store confidence
  * FR-9 neighborhood traversal for cross-document reasoning
  * FR-14 incremental updates (add more documents without a rebuild)

Nodes are keyed by a normalised id so 'Harry Potter' and 'harry potter'
collapse into one entity. Every node and edge carries provenance (the chunk
ids that support it) and an accumulated confidence.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


class KnowledgeGraph:
    def __init__(self) -> None:
        # id -> {name, type, description, aliases:set, mentions:set(chunk_id), confidence}
        self.nodes: dict[str, dict] = {}
        # list of {source, target, type, evidence, confidence, provenance:set}
        self.edges: list[dict] = []
        self._edge_index: dict[tuple[str, str, str], dict] = {}

    # -- mutation ----------------------------------------------------------
    def add_entity(
        self,
        name: str,
        type: str = "CONCEPT",
        description: str = "",
        chunk_id: str | None = None,
        confidence: float = 0.7,
    ) -> str:
        node_id = normalize(name)
        node = self.nodes.get(node_id)
        if node is None:
            node = {
                "id": node_id,
                "name": name,
                "type": type,
                "description": description,
                "aliases": set(),
                "mentions": set(),
                "confidence": confidence,
            }
            self.nodes[node_id] = node
        else:
            # Merge: keep the longer description, remember alternate surface forms.
            if name != node["name"]:
                node["aliases"].add(name)
            if len(description) > len(node["description"]):
                node["description"] = description
            node["confidence"] = min(1.0, node["confidence"] + 0.05)
        if chunk_id:
            node["mentions"].add(chunk_id)
        return node_id

    def add_relationship(
        self,
        source: str,
        target: str,
        type: str = "related_to",
        evidence: str = "",
        confidence: float = 0.7,
        chunk_id: str | None = None,
    ) -> None:
        s, t = normalize(source), normalize(target)
        if s not in self.nodes or t not in self.nodes or s == t:
            return
        key = (s, t, type)
        edge = self._edge_index.get(key)
        if edge is None:
            edge = {
                "source": s,
                "target": t,
                "type": type,
                "evidence": evidence,
                "confidence": confidence,
                "provenance": set(),
            }
            self._edge_index[key] = edge
            self.edges.append(edge)
        else:
            edge["confidence"] = min(1.0, edge["confidence"] + 0.05)
            if len(evidence) > len(edge["evidence"]):
                edge["evidence"] = evidence
        if chunk_id:
            edge["provenance"].add(chunk_id)

    # -- query -------------------------------------------------------------
    def find_entities(self, text: str) -> list[str]:
        """Return node ids whose name/alias appears in `text` (case-insensitive)."""
        low = text.lower()
        hits = []
        for node_id, node in self.nodes.items():
            surfaces = [node["name"], *node["aliases"]]
            if any(s.lower() in low for s in surfaces):
                hits.append(node_id)
        return hits

    def neighborhood(self, node_ids: Iterable[str], hops: int = 1) -> dict:
        """Return the subgraph within `hops` of the seed nodes."""
        frontier = set(node_ids)
        visited = set(frontier)
        collected_edges = []
        for _ in range(max(0, hops)):
            next_frontier = set()
            for edge in self.edges:
                if edge["source"] in frontier or edge["target"] in frontier:
                    collected_edges.append(edge)
                    next_frontier.update({edge["source"], edge["target"]})
            new = next_frontier - visited
            visited |= new
            frontier = new
            if not frontier:
                break
        return {
            "nodes": {nid: self.nodes[nid] for nid in visited if nid in self.nodes},
            "edges": _dedup_edges(collected_edges),
        }

    def stats(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            by_type[n["type"]] += 1
        return {
            "entities": len(self.nodes),
            "relationships": len(self.edges),
            "entity_types": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        }

    # -- persistence -------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [
                {**n, "aliases": sorted(n["aliases"]), "mentions": sorted(n["mentions"])}
                for n in self.nodes.values()
            ],
            "edges": [
                {**e, "provenance": sorted(e["provenance"])} for e in self.edges
            ],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        kg = cls()
        path = Path(path)
        if not path.exists():
            return kg
        payload = json.loads(path.read_text(encoding="utf-8"))
        for n in payload.get("nodes", []):
            n["aliases"] = set(n.get("aliases", []))
            n["mentions"] = set(n.get("mentions", []))
            kg.nodes[n["id"]] = n
        for e in payload.get("edges", []):
            e["provenance"] = set(e.get("provenance", []))
            kg.edges.append(e)
            kg._edge_index[(e["source"], e["target"], e["type"])] = e
        return kg


def _dedup_edges(edges: list[dict]) -> list[dict]:
    seen, out = set(), []
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
