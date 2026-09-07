"""allow long Sentinel source references

Revision ID: 20260830_0006
Revises: 20260829_0005
Create Date: 2026-08-30 15:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260830_0006"
down_revision = "20260829_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "satellite_images",
        "source_reference",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "satellite_images",
        "source_reference",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
