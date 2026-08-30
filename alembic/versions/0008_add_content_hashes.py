"""add content_hash to documents and chunks (incremental updates)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-24
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_chunks_content_hash", table_name="chunks")
    op.drop_column("chunks", "content_hash")
    op.drop_column("documents", "content_hash")
