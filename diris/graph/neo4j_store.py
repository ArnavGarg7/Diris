"""Neo4j implementation of GraphStore (M7).

Model:
  (:Entity {entity_id, user_id, name, type})
     -[:REL {rel_id, user_id, type, confidence, evidence, document_id, chunk_id}]->
  (:Entity ...)

Relationship *types* are stored as a `type` property on a generic :REL edge,
because Cypher can't parameterize the edge label without the APOC plugin.
Idempotency comes from MERGE on the unique entity_id / rel_id.
"""
from __future__ import annotations

from neo4j import GraphDatabase

from ..config import settings
from .base import GraphStore


class Neo4jGraphStore(GraphStore):
    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        self.driver = GraphDatabase.driver(
            uri or settings.neo4j_uri,
            auth=(user or settings.neo4j_user, password or settings.neo4j_password),
        )
        self._ensure_constraints()

    def _ensure_constraints(self) -> None:
        with self.driver.session() as s:
            s.run(
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE"
            )

    def upsert_entity(self, entity_id: int, user_id: int, name: str, type: str) -> None:
        with self.driver.session() as s:
            s.run(
                "MERGE (e:Entity {entity_id: $eid}) "
                "SET e.user_id = $uid, e.name = $name, e.type = $type",
                eid=entity_id, uid=user_id, name=name, type=type,
            )

    def upsert_relationship(
        self, *, rel_id: int, user_id: int, source_id: int, target_id: int,
        type: str, confidence: float, evidence: str | None,
        document_id: int, chunk_id: int,
    ) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MATCH (a:Entity {entity_id: $src}), (b:Entity {entity_id: $tgt})
                MERGE (a)-[r:REL {rel_id: $rid}]->(b)
                SET r.user_id = $uid, r.type = $type, r.confidence = $conf,
                    r.evidence = $ev, r.document_id = $did, r.chunk_id = $cid
                """,
                src=source_id, tgt=target_id, rid=rel_id, uid=user_id, type=type,
                conf=confidence, ev=evidence, did=document_id, cid=chunk_id,
            )

    def delete_document_relationships(self, document_id: int) -> None:
        with self.driver.session() as s:
            s.run("MATCH ()-[r:REL {document_id: $did}]->() DELETE r", did=document_id)

    def delete_entities(self, entity_ids: list[int]) -> None:
        if not entity_ids:
            return
        with self.driver.session() as s:
            # DETACH also drops any remaining edges touching these nodes.
            s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids DETACH DELETE e", ids=entity_ids)

    def neighborhood(self, user_id: int, entity_id: int, hops: int = 1) -> dict | None:
        hops = max(1, min(int(hops), 3))  # bound the traversal (also safe to inline)
        with self.driver.session() as s:
            center = s.run(
                "MATCH (e:Entity {entity_id: $eid, user_id: $uid}) "
                "RETURN e.entity_id AS id, e.name AS name, e.type AS type",
                eid=entity_id, uid=user_id,
            ).single()
            if center is None:
                return None

            nodes = {center["id"]: {"entity_id": center["id"], "name": center["name"], "type": center["type"]}}
            edges: list[dict] = []
            records = s.run(
                f"""
                MATCH (e:Entity {{entity_id: $eid, user_id: $uid}})-[rel:REL*1..{hops}]-(:Entity)
                UNWIND rel AS r
                RETURN DISTINCT
                    startNode(r).entity_id AS s, startNode(r).name AS sn, startNode(r).type AS st,
                    endNode(r).entity_id AS t, endNode(r).name AS tn, endNode(r).type AS tt,
                    r.type AS type, r.confidence AS confidence
                """,
                eid=entity_id, uid=user_id,
            )
            for rec in records:
                nodes[rec["s"]] = {"entity_id": rec["s"], "name": rec["sn"], "type": rec["st"]}
                nodes[rec["t"]] = {"entity_id": rec["t"], "name": rec["tn"], "type": rec["tt"]}
                edges.append(
                    {"source": rec["s"], "target": rec["t"], "type": rec["type"], "confidence": rec["confidence"]}
                )
            return {"nodes": list(nodes.values()), "edges": edges}

    def full_graph(self, user_id: int, limit: int = 1000) -> dict:
        with self.driver.session() as s:
            # 1. Fetch relationships first so interconnected networks across multiple
            # documents are guaranteed to be represented with their endpoints.
            edge_recs = s.run(
                """
                MATCH (a:Entity {user_id: $uid})-[r:REL]->(b:Entity {user_id: $uid})
                RETURN a.entity_id AS s, a.name AS sn, a.type AS st,
                       b.entity_id AS t, b.name AS tn, b.type AS tt,
                       r.type AS type, r.confidence AS confidence
                LIMIT $lim
                """,
                uid=user_id, lim=limit,
            )
            nodes: dict[int, dict] = {}
            edges: list[dict] = []
            for r in edge_recs:
                nodes[r["s"]] = {"entity_id": r["s"], "name": r["sn"], "type": r["st"]}
                nodes[r["t"]] = {"entity_id": r["t"], "name": r["tn"], "type": r["tt"]}
                edges.append(
                    {"source": r["s"], "target": r["t"], "type": r["type"], "confidence": r["confidence"]}
                )

            # 2. Fill remaining headroom with any unlinked/singleton entities
            if len(nodes) < limit:
                remain = limit - len(nodes)
                node_recs = s.run(
                    """
                    MATCH (e:Entity {user_id: $uid})
                    WHERE NOT e.entity_id IN $existing
                    RETURN e.entity_id AS id, e.name AS name, e.type AS type
                    LIMIT $lim
                    """,
                    uid=user_id, existing=list(nodes.keys()), lim=remain,
                )
                for r in node_recs:
                    nodes[r["id"]] = {"entity_id": r["id"], "name": r["name"], "type": r["type"]}

            return {"nodes": list(nodes.values()), "edges": edges}

    def shortest_path(self, user_id: int, source_id: int, target_id: int) -> dict:
        with self.driver.session() as s:
            rec = s.run(
                # max 6 hops; undirected so it finds a path regardless of edge direction
                "MATCH (a:Entity {entity_id: $src, user_id: $uid}), "
                "(b:Entity {entity_id: $tgt, user_id: $uid}), "
                "p = shortestPath((a)-[:REL*..6]-(b)) RETURN p",
                src=source_id, tgt=target_id, uid=user_id,
            ).single()
            if rec is None:
                return {"nodes": [], "edges": [], "found": False}
            path = rec["p"]
            nodes = [
                {"entity_id": n["entity_id"], "name": n["name"], "type": n["type"]}
                for n in path.nodes
            ]
            edges = [
                {
                    "source": rel.start_node["entity_id"], "target": rel.end_node["entity_id"],
                    "type": rel.get("type"), "confidence": rel.get("confidence"),
                }
                for rel in path.relationships
            ]
            return {"nodes": nodes, "edges": edges, "found": True}

    def clear(self) -> None:
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        self.driver.close()
