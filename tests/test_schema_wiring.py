"""Offline checks that the ORM schema is wired as intended (no DB needed)."""
from diris.db import models  # noqa: F401  (registers models on metadata)
from diris.db.session import Base


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert {
        "users",
        "documents",
        "document_metadata",
        "chunks",
        "document_processing_status",
    } <= tables


def test_chunks_columns_and_unique_constraint():
    chunks = Base.metadata.tables["chunks"]
    assert {"document_id", "chunk_index", "content", "char_count"} <= set(chunks.columns.keys())
    constraint_names = {c.name for c in chunks.constraints}
    assert "uq_chunks_document_id_chunk_index" in constraint_names


def test_document_has_chunk_and_status_relationships():
    rels = {r.key for r in models.Document.__mapper__.relationships}
    assert {"chunks", "processing_status_history", "metadata_items"} <= rels
