"""add a FULLTEXT index on chunks.content for keyword search

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL InnoDB FULLTEXT index -> enables MATCH(content) AGAINST(...) keyword search.
    op.create_index(
        "ix_chunks_content_fulltext", "chunks", ["content"], mysql_prefix="FULLTEXT"
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_content_fulltext", table_name="chunks")
