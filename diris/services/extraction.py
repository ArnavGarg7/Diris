"""Orchestrates entity/relationship extraction for a whole document.

For each chunk: run the extractor, resolve every entity to a canonical entity,
then persist relationships between the resolved entities. Idempotency across
reprocessing is largely automatic: deleting a document's chunks cascades to its
entity_mentions and relationships, so we only clean up orphaned entities here.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from ..db.repositories import (
    ChunkRepository,
    DocumentRepository,
    EntityRepository,
    RelationshipRepository,
)
from ..extraction import get_extractor
from ..vectorstore import get_entity_index
from .resolution import EntityResolver

log = logging.getLogger("diris.extraction")


def _extract_with_retry(extractor, text: str, retries: int = 3, base_delay: float = 5.0):
    """Call extractor.extract() with exponential-backoff retry on rate-limit errors.

    Groq free tier is strict (30 RPM); a 429 must not abort the whole document.
    """
    from ..extraction.schema import Extraction  # local to avoid circular

    for attempt in range(retries):
        try:
            return extractor.extract(text)
        except Exception as exc:
            msg = str(exc).lower()
            is_rate_limit = any(k in msg for k in ("429", "rate limit", "rate_limit", "too many"))
            if is_rate_limit and attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                log.warning("Rate-limit on extraction attempt %d/%d; retrying in %.0fs", attempt + 1, retries, wait)
                time.sleep(wait)
            else:
                log.warning("Extraction attempt %d/%d failed: %s", attempt + 1, retries, exc)
                if attempt == retries - 1:
                    # Return empty rather than crashing the whole chunk loop
                    return Extraction(entities=[], relationships=[])
                raise
    # unreachable
    from ..extraction.schema import Extraction
    return Extraction(entities=[], relationships=[])


def extract_document(
    db,
    document_id: int,
    only_chunk_ids: list[int] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, int]:
    """Extract entities/relationships for a document's chunks.

    `progress(done, total)` (optional) is invoked after each chunk so callers
    can report live progress on the otherwise-slow extraction loop.
    """
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

    total = len(chunks)
    n_entities = n_relationships = 0
    for done, chunk in enumerate(chunks, start=1):
        try:
            extraction = _extract_with_retry(extractor, chunk.content)

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
                # Map both the raw extracted name AND the canonical name so relationship
                # endpoint matching works regardless of which form the LLM used.
                resolved[ent.name] = entity.id
                resolved[entity.canonical_name] = entity.id
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
            db.commit()
        except Exception as exc:
            log.warning("Chunk %s extraction error: %s", chunk.id, exc)
            db.rollback()

        if progress is not None:
            progress(done, total)
        time.sleep(0.2)

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
