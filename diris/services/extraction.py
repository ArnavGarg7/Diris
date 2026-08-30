"""Orchestrates entity/relationship extraction for a whole document.

For each chunk: run the extractor, resolve every entity to a canonical entity,
then persist relationships between the resolved entities. Idempotency across
reprocessing is largely automatic: deleting a document's chunks cascades to its
entity_mentions and relationships, so we only clean up orphaned entities here.
"""
from __future__ import annotations

from ..db.repositories import (
    ChunkRepository,
    DocumentRepository,
    EntityRepository,
    RelationshipRepository,
)
from ..extraction import get_extractor
from ..vectorstore import get_entity_index
from .resolution import EntityResolver


def extract_document(
    db, document_id: int, only_chunk_ids: list[int] | None = None
) -> dict[str, int]:
    document = DocumentRepository(db).get(document_id)
    if document is None:
        return {"entities": 0, "relationships": 0}

    chunks = ChunkRepository(db).list_for_document(document_id)
    if only_chunk_ids is not None:  # incremental: extract only the added chunks
        wanted = set(only_chunk_ids)
        chunks = [c for c in chunks if c.id in wanted]
    extractor = get_extractor()
    resolver = EntityResolver(db, get_entity_index())
    rel_repo = RelationshipRepository(db)

    n_entities = n_relationships = 0
    for chunk in chunks:
        extraction = extractor.extract(chunk.content)

        # Resolve each extracted entity to a canonical entity for this chunk.
        resolved: dict[str, int] = {}  # extracted-name -> canonical entity id
        for ent in extraction.entities:
            entity = resolver.resolve(
                user_id=document.user_id,
                name=ent.name,
                type=ent.type,
                description=ent.description or None,
                chunk_id=chunk.id,
                document_id=document_id,
            )
            resolved[ent.name] = entity.id
            n_entities += 1

        # Persist relationships between resolved entities.
        for rel in extraction.relationships:
            src = resolved.get(rel.source)
            tgt = resolved.get(rel.target)
            if src is None or tgt is None or src == tgt:
                continue
            rel_repo.create(
                user_id=document.user_id,
                source_entity_id=src,
                target_entity_id=tgt,
                type=rel.type,
                evidence=rel.evidence or None,
                confidence=rel.confidence,
                chunk_id=chunk.id,
                document_id=document_id,
            )
            n_relationships += 1

    # Drop entities left with no mentions (e.g. after reprocessing) and de-index them.
    orphan_ids = EntityRepository(db).delete_orphans(document.user_id)
    _deindex_entities(orphan_ids)

    return {"entities": n_entities, "relationships": n_relationships}


def _deindex_entities(entity_ids: list[int]) -> None:
    """Remove orphaned entities from the name-embedding index (best-effort).

    Entities are keyed in the index by their own id, so we delete by id.
    """
    if not entity_ids:
        return
    index = get_entity_index()
    try:
        index.collection.delete(ids=[str(i) for i in entity_ids])  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover  (best-effort cleanup)
        pass
