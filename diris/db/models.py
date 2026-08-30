"""ORM models. Each class maps to one MySQL table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    # Nearest heading this chunk falls under (provenance); null if none (M10).
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


class Entity(Base):
    """A resolved knowledge entity in a user's library (M6). MySQL is the source
    of truth; M7 projects these into Neo4j for traversal."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aliases: Mapped[list["EntityAlias"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["EntityMention"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_entities_user_normalized", "user_id", "normalized_name"),
    )

    def __repr__(self) -> str:
        return f"<Entity id={self.id} name={self.canonical_name!r} type={self.type}>"


class EntityAlias(Base):
    """An alternate surface form that resolves to the same entity."""

    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    alias: Mapped[str] = mapped_column(String(512), nullable=False)

    entity: Mapped["Entity"] = relationship(back_populates="aliases")


class EntityMention(Base):
    """Provenance: a place (chunk) where an entity was mentioned."""

    __tablename__ = "entity_mentions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    surface_text: Mapped[str] = mapped_column(String(512), nullable=False)

    entity: Mapped["Entity"] = relationship(back_populates="mentions")


class Relationship(Base):
    """A typed, evidence-backed edge between two entities (M6). Source of truth
    in MySQL; projected into Neo4j in M7."""

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Relationship {self.source_entity_id}-[{self.type}]->{self.target_entity_id}>"
