"""ORM models. Each class maps to one MySQL table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
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
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )
    processing_status_history: Mapped[list["DocumentProcessingStatus"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentProcessingStatus.created_at",
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


class Chunk(Base):
    """A contiguous slice of a document's text — the unit of retrieval/provenance.

    The chunk TEXT is the system of record here in MySQL. Its embedding (vector)
    will live in ChromaDB (M5), keyed by this chunk's id. That id is the join key
    across MySQL / ChromaDB / Neo4j.
    """

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)  # 0-based order in doc
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    # A document can't have two chunks at the same index.
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_id_chunk_index"),
    )

    def __repr__(self) -> str:
        return f"<Chunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"


class DocumentProcessingStatus(Base):
    """Append-only history of processing state transitions (audit + observability).

    The document's *current* state is denormalized onto `documents.status` for
    fast filtering; this table is the full transition log with optional stage and
    error message.
    """

    __tablename__ = "document_processing_status"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # uploaded|processing|done|failed
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="processing_status_history")

    def __repr__(self) -> str:
        return f"<ProcessingStatus doc={self.document_id} status={self.status!r}>"
