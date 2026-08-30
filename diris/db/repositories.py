"""Repositories: the only code that issues database queries.

Keeping DB access here (not in routes or services) makes the business logic
testable and the storage swappable.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session


def content_hash(text_value: str) -> str:
    """SHA-256 hex digest of a string (used for change detection)."""
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()

from .models import (
    Chunk,
    Conversation,
    Document,
    DocumentMetadata,
    DocumentProcessingStatus,
    Entity,
    EntityAlias,
    EntityMention,
    Message,
    Relationship,
    User,
)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)  # populate server-generated id / created_at
        return user


class DocumentRepository:
    """All document/metadata queries. Every read is scoped by user_id."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        original_filename: str,
        stored_path: str,
        content_type: str,
        size_bytes: int,
        status: str = "uploaded",
        metadata: dict[str, str] | None = None,
    ) -> Document:
        doc = Document(
            user_id=user_id,
            original_filename=original_filename,
            stored_path=stored_path,
            content_type=content_type,
            size_bytes=size_bytes,
            status=status,
        )
        for key, value in (metadata or {}).items():
            doc.metadata_items.append(
                DocumentMetadata(meta_key=key, meta_value=str(value))
            )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def list_for_user(self, user_id: int) -> list[Document]:
        return list(
            self.db.execute(
                select(Document)
                .where(Document.user_id == user_id)
                .order_by(Document.created_at.desc())
            ).scalars()
        )

    def get(self, document_id: int) -> Document | None:
        """Unscoped fetch by id. INTERNAL ONLY (e.g. the background worker) —
        user-facing paths must use get_for_user to enforce ownership."""
        return self.db.get(Document, document_id)

    def get_for_user(self, document_id: int, user_id: int) -> Document | None:
        # Ownership is enforced in the WHERE clause: another user's id returns None.
        return self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        ).scalar_one_or_none()

    def set_content_hash(self, document_id: int, hash_value: str) -> None:
        document = self.db.get(Document, document_id)
        if document is not None:
            document.content_hash = hash_value
            self.db.commit()

    def set_metadata(self, document_id: int, key: str, value: str) -> None:
        """Upsert a single metadata key (delete existing rows for the key, insert)."""
        self.db.execute(
            delete(DocumentMetadata).where(
                DocumentMetadata.document_id == document_id,
                DocumentMetadata.meta_key == key,
            )
        )
        self.db.add(
            DocumentMetadata(document_id=document_id, meta_key=key, meta_value=str(value))
        )
        self.db.commit()

    def delete(self, document: Document) -> None:
        self.db.delete(document)  # ORM cascade removes metadata/chunks/status rows too
        self.db.commit()


class ChunkRepository:
    """Chunk persistence. Bulk inserts are atomic (one transaction)."""

    def __init__(self, db: Session):
        self.db = db

    def add_chunks(
        self, document_id: int, texts: list[str], sections: list[str | None] | None = None
    ) -> list[Chunk]:
        """Insert all chunks for a document in a single transaction (all-or-nothing)."""
        sections = sections or [None] * len(texts)
        chunks = [
            Chunk(
                document_id=document_id,
                chunk_index=i,
                content=text,
                char_count=len(text),
                section=sections[i],
                content_hash=content_hash(text),
            )
            for i, text in enumerate(texts)
        ]
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def insert_chunks(
        self, document_id: int, items: list[tuple[int, str, str | None]]
    ) -> list[Chunk]:
        """Insert specific chunks with explicit (index, text, section) — used by
        incremental update to add only the changed chunks."""
        chunks = [
            Chunk(
                document_id=document_id, chunk_index=i, content=t,
                char_count=len(t), section=s, content_hash=content_hash(t),
            )
            for (i, t, s) in items
        ]
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def delete_by_ids(self, chunk_ids: list[int]) -> None:
        if not chunk_ids:
            return
        self.db.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))
        self.db.commit()

    def list_for_document(self, document_id: int) -> list[Chunk]:
        return list(
            self.db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index)
            ).scalars()
        )

    def delete_for_document(self, document_id: int) -> int:
        """Remove a document's chunks (used by M13 re-processing). Returns row count."""
        result = self.db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        self.db.commit()
        return result.rowcount or 0

    def keyword_search(self, user_id: int, query: str, limit: int = 10) -> list[int]:
        """Full-text keyword search over a user's chunks. Returns chunk ids ranked
        by MySQL relevance (MATCH ... AGAINST, natural-language mode)."""
        rows = self.db.execute(
            text(
                """
                SELECT c.id AS id
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.user_id = :uid
                  AND MATCH(c.content) AGAINST(:q IN NATURAL LANGUAGE MODE)
                ORDER BY MATCH(c.content) AGAINST(:q IN NATURAL LANGUAGE MODE) DESC
                LIMIT :lim
                """
            ),
            {"uid": user_id, "q": query, "lim": limit},
        ).all()
        return [r[0] for r in rows]


class ProcessingStatusRepository:
    """Records processing transitions and keeps documents.status in sync."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        document_id: int,
        status: str,
        *,
        stage: str | None = None,
        message: str | None = None,
        update_document: bool = True,
    ) -> DocumentProcessingStatus:
        """Append a history row and (optionally) update the document's current status.

        Both writes commit together so the denormalized status and the history
        never disagree.
        """
        event = DocumentProcessingStatus(
            document_id=document_id, status=status, stage=stage, message=message
        )
        self.db.add(event)
        if update_document:
            document = self.db.get(Document, document_id)
            if document is not None:
                document.status = status
        self.db.commit()
        self.db.refresh(event)
        return event

    def history_for_document(self, document_id: int) -> list[DocumentProcessingStatus]:
        return list(
            self.db.execute(
                select(DocumentProcessingStatus)
                .where(DocumentProcessingStatus.document_id == document_id)
                .order_by(DocumentProcessingStatus.created_at)
            ).scalars()
        )


class EntityRepository:
    """Resolved-entity registry + aliases + provenance mentions. User-scoped."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, user_id: int, canonical_name: str, normalized_name: str,
        type: str, description: str | None = None,
    ) -> Entity:
        entity = Entity(
            user_id=user_id, canonical_name=canonical_name,
            normalized_name=normalized_name, type=type, description=description,
        )
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get(self, entity_id: int) -> Entity | None:
        return self.db.get(Entity, entity_id)

    def get_for_user(self, entity_id: int, user_id: int) -> Entity | None:
        return self.db.execute(
            select(Entity).where(Entity.id == entity_id, Entity.user_id == user_id)
        ).scalar_one_or_none()

    def find_by_normalized(self, user_id: int, normalized_name: str) -> Entity | None:
        return self.db.execute(
            select(Entity).where(
                Entity.user_id == user_id, Entity.normalized_name == normalized_name
            )
        ).scalars().first()

    def find_by_alias(self, user_id: int, normalized_alias: str) -> Entity | None:
        return self.db.execute(
            select(Entity)
            .join(EntityAlias, EntityAlias.entity_id == Entity.id)
            .where(
                Entity.user_id == user_id,
                func.lower(func.trim(EntityAlias.alias)) == normalized_alias,
            )
        ).scalars().first()

    def add_alias_if_new(self, entity: Entity, alias: str) -> None:
        norm = alias.strip().lower()
        if norm == entity.normalized_name:
            return
        existing = {a.alias.strip().lower() for a in entity.aliases}
        if norm not in existing:
            self.db.add(EntityAlias(entity_id=entity.id, alias=alias))

    def add_mention(
        self, entity_id: int, chunk_id: int, document_id: int, surface_text: str
    ) -> None:
        self.db.add(
            EntityMention(
                entity_id=entity_id, chunk_id=chunk_id,
                document_id=document_id, surface_text=surface_text,
            )
        )

    def list_for_user(self, user_id: int) -> list[Entity]:
        return list(
            self.db.execute(
                select(Entity).where(Entity.user_id == user_id).order_by(Entity.canonical_name)
            ).scalars()
        )

    def for_document(self, document_id: int, user_id: int) -> list[Entity]:
        return list(
            self.db.execute(
                select(Entity)
                .join(EntityMention, EntityMention.entity_id == Entity.id)
                .where(Entity.user_id == user_id, EntityMention.document_id == document_id)
                .distinct()
                .order_by(Entity.canonical_name)
            ).scalars()
        )

    def chunk_ids_for_entities(self, entity_ids: list[int], limit: int = 10) -> list[int]:
        """Chunks that mention any of these entities, ranked by mention count."""
        if not entity_ids:
            return []
        rows = self.db.execute(
            select(EntityMention.chunk_id, func.count().label("cnt"))
            .where(EntityMention.entity_id.in_(entity_ids))
            .group_by(EntityMention.chunk_id)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        return [r[0] for r in rows]

    def delete_orphans(self, user_id: int) -> list[int]:
        """Delete this user's entities that have no mentions; return their ids
        (so the caller can drop them from the vector index too)."""
        orphan_ids = [
            row[0]
            for row in self.db.execute(
                select(Entity.id)
                .outerjoin(EntityMention, EntityMention.entity_id == Entity.id)
                .where(Entity.user_id == user_id, EntityMention.id.is_(None))
            ).all()
        ]
        if orphan_ids:
            self.db.execute(delete(Entity).where(Entity.id.in_(orphan_ids)))
            self.db.commit()
        return orphan_ids


class RelationshipRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, user_id: int, source_entity_id: int, target_entity_id: int,
        type: str, evidence: str | None, confidence: float,
        chunk_id: int, document_id: int,
    ) -> Relationship:
        rel = Relationship(
            user_id=user_id, source_entity_id=source_entity_id,
            target_entity_id=target_entity_id, type=type, evidence=evidence,
            confidence=confidence, chunk_id=chunk_id, document_id=document_id,
        )
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def for_entity(self, entity_id: int) -> list[Relationship]:
        return list(
            self.db.execute(
                select(Relationship).where(
                    or_(
                        Relationship.source_entity_id == entity_id,
                        Relationship.target_entity_id == entity_id,
                    )
                )
            ).scalars()
        )

    def for_user(self, user_id: int) -> list[Relationship]:
        return list(
            self.db.execute(
                select(Relationship).where(Relationship.user_id == user_id)
            ).scalars()
        )

    def for_document(self, document_id: int) -> list[Relationship]:
        return list(
            self.db.execute(
                select(Relationship).where(Relationship.document_id == document_id)
            ).scalars()
        )


class ConversationRepository:
    """Conversations + their message turns. User-scoped."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int) -> Conversation:
        conv = Conversation(user_id=user_id)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def get_for_user(self, conversation_id: int, user_id: int) -> Conversation | None:
        return self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int) -> list[Conversation]:
        return list(
            self.db.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.created_at.desc())
            ).scalars()
        )

    def messages(self, conversation_id: int) -> list[Message]:
        return list(
            self.db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
            ).scalars()
        )

    def recent_messages(self, conversation_id: int, limit: int = 6) -> list[Message]:
        """Last `limit` messages, returned in chronological order (for the rewrite)."""
        newest_first = list(
            self.db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
            ).scalars()
        )
        return list(reversed(newest_first))

    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg
