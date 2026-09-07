"""remove obsolete hotspot spatial column

Revision ID: 20260907_0007
Revises: 20260830_0006
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op


revision = "20260907_0007"
down_revision = "20260830_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fire_hotspots_geometry_gist")
    op.execute("ALTER TABLE fire_hotspots DROP COLUMN IF EXISTS geometry")


def downgrade() -> None:
    pass
