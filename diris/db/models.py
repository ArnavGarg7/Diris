"""ORM models. Each class maps to one MySQL table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # unique + indexed: two people can't register the same email, and lookups are fast.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # helpful in logs/tests
        return f"<User id={self.id} email={self.email!r}>"


class Document(Base):
    """A file a user uploaded. The bytes live on disk; this row is the metadata."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Lifecycle state; M4's processing pipeline advances this beyond "uploaded".
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="uploaded")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # NB: attribute is NOT named `metadata` — that's reserved by SQLAlchemy's Base.
    metadata_items: Mapped[list["DocumentMetadata"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} user_id={self.user_id} name={self.original_filename!r}>"


class DocumentMetadata(Base):
    """Flexible per-document key/value attributes (extensible without schema changes)."""

    __tablename__ = "document_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # meta_key/meta_value avoid the MySQL reserved words `key`/`value`.
    meta_key: Mapped[str] = mapped_column(String(128), nullable=False)
    meta_value: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="metadata_items")
