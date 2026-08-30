"""add section column to chunks (provenance)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-24
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("section", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "section")
