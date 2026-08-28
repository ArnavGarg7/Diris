"""Repositories: the only code that issues database queries.

Keeping DB access here (not in routes or services) makes the business logic
testable and the storage swappable.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    Chunk,
    Document,
    DocumentMetadata,
    DocumentProcessingStatus,
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

    def add_chunks(self, document_id: int, texts: list[str]) -> list[Chunk]:
        """Insert all chunks for a document in a single transaction (all-or-nothing)."""
        chunks = [
            Chunk(
                document_id=document_id,
                chunk_index=i,
                content=text,
                char_count=len(text),
            )
            for i, text in enumerate(texts)
        ]
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

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
