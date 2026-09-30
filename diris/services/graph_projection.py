"""Project a document's entities + relationships from MySQL into Neo4j (M7).

MySQL is the source of truth; this builds the Neo4j read model. Idempotent:
we clear the document's edges first, then MERGE entities and edges (so nodes
shared across documents are updated, never duplicated).
"""
from __future__ import annotations

from ..db.repositories import (
    DocumentRepository,
    EntityRepository,
    RelationshipRepository,
)
from ..graph import get_graph_store


def project_document(db, document_id: int) -> dict[str, int]:
    document = DocumentRepository(db).get(document_id)
    if document is None:
        return {"nodes": 0, "edges": 0}

    entities = EntityRepository(db).for_document(document_id, document.user_id)
    relationships = RelationshipRepository(db).for_document(document_id)

    store = get_graph_store()
    store.delete_document_relationships(document_id)  # idempotent re-projection

    for entity in entities:
        store.upsert_entity(entity.id, document.user_id, entity.canonical_name, entity.type)

    # Guarantee all relationship endpoint entities exist in Neo4j before linking
    endpoint_ids = {r.source_entity_id for r in relationships} | {r.target_entity_id for r in relationships}
    missing_ids = endpoint_ids - {e.id for e in entities}
    if missing_ids:
        ent_repo = EntityRepository(db)
        for mid in missing_ids:
            ent = ent_repo.get(mid)
            if ent is not None:
                store.upsert_entity(ent.id, document.user_id, ent.canonical_name, ent.type)

    for rel in relationships:
        store.upsert_relationship(
            rel_id=rel.id, user_id=document.user_id,
            source_id=rel.source_entity_id, target_id=rel.target_entity_id,
            type=rel.type, confidence=rel.confidence, evidence=rel.evidence,
            document_id=document_id, chunk_id=rel.chunk_id,
        )

    return {"nodes": len(entities), "edges": len(relationships)}
