"""Entity resolution: map an extracted mention to a canonical entity.

Strategy (precision-first):
  1. exact normalized-name match (same user)        -> merge
  2. exact alias match (same user)                   -> merge
  3. embedding similarity (same user + same type)    -> merge if score >= threshold
  4. otherwise                                       -> create a new entity

We prefer UNDER-merging: a high threshold means a wrong merge (two different
real entities collapsed) is unlikely, at the cost of occasionally missing a
merge. Wrong merges are much harder to recover from than misses.
"""
from __future__ import annotations

import re

from ..config import settings
from ..db.models import Entity
from ..db.repositories import EntityRepository
from ..vectorstore.base import VectorStoreBase


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


class EntityResolver:
    def __init__(
        self,
        db,
        entity_index: VectorStoreBase,
        threshold: float | None = None,
    ):
        self.db = db
        self.repo = EntityRepository(db)
        self.index = entity_index
        self.threshold = threshold if threshold is not None else settings.resolution_threshold

    def resolve(
        self,
        *,
        user_id: int,
        name: str,
        type: str,
        description: str | None,
        chunk_id: int,
        document_id: int,
    ) -> Entity:
        normalized = normalize(name)

        existing = self.repo.find_by_normalized(user_id, normalized)
        if existing is None:
            existing = self.repo.find_by_alias(user_id, normalized)
        if existing is None:
            existing = self._match_by_embedding(user_id, name, type)

        if existing is not None:
            self._merge(existing, name, description, chunk_id, document_id)
            return existing

        return self._create(user_id, name, normalized, type, description, chunk_id, document_id)

    # -- internals ---------------------------------------------------------
    def _match_by_embedding(self, user_id: int, name: str, type: str) -> Entity | None:
        matches = self.index.query(
            name, top_k=1, where={"user_id": user_id, "type": type}
        )
        if matches and matches[0].score >= self.threshold:
            # For the entity index, the stored id is the entity id.
            return self.repo.get(matches[0].chunk_id)
        return None

    def _merge(
        self, entity: Entity, name: str, description: str | None,
        chunk_id: int, document_id: int,
    ) -> None:
        self.repo.add_alias_if_new(entity, name)
        if description and len(description) > len(entity.description or ""):
            entity.description = description
        self.repo.add_mention(entity.id, chunk_id, document_id, surface_text=name)
        self.db.commit()

    def _create(
        self, user_id: int, name: str, normalized: str, type: str,
        description: str | None, chunk_id: int, document_id: int,
    ) -> Entity:
        entity = self.repo.create(
            user_id=user_id, canonical_name=name,
            normalized_name=normalized, type=type, description=description,
        )
        self.repo.add_mention(entity.id, chunk_id, document_id, surface_text=name)
        self.db.commit()
        # Index the entity name so future mentions can resolve to it by similarity.
        self.index.upsert(
            ids=[str(entity.id)],
            texts=[entity.canonical_name],
            metadatas=[{"user_id": user_id, "type": type, "entity_id": entity.id}],
        )
        return entity
