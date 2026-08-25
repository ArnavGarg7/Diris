"""Repositories: the only code that issues database queries.

Keeping DB access here (not in routes or services) makes the business logic
testable and the storage swappable.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, DocumentMetadata, User


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

    def get_for_user(self, document_id: int, user_id: int) -> Document | None:
        # Ownership is enforced in the WHERE clause: another user's id returns None.
        return self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        ).scalar_one_or_none()

    def delete(self, document: Document) -> None:
        self.db.delete(document)  # ORM cascade removes metadata rows too
        self.db.commit()
