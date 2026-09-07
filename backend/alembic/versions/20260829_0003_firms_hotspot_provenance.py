"""firms hotspot provenance

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_0003"
down_revision = "20260829_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fire_hotspots", sa.Column("provider", sa.String(80), nullable=False, server_default="unknown"))
    op.add_column("fire_hotspots", sa.Column("source_record_id", sa.String(160), nullable=True))
    op.add_column("fire_hotspots", sa.Column("retrieved_at", sa.DateTime(), nullable=True))
    op.add_column("fire_hotspots", sa.Column("satellite", sa.String(80), nullable=True))
    op.add_column("fire_hotspots", sa.Column("instrument", sa.String(80), nullable=True))
    op.add_column("fire_hotspots", sa.Column("brightness", sa.Float(), nullable=True))
    op.add_column("fire_hotspots", sa.Column("frp", sa.Float(), nullable=True))
    op.add_column("fire_hotspots", sa.Column("scan", sa.Float(), nullable=True))
    op.add_column("fire_hotspots", sa.Column("track", sa.Float(), nullable=True))
    op.add_column("fire_hotspots", sa.Column("daynight", sa.String(8), nullable=True))
    op.add_column("fire_hotspots", sa.Column("quality_status", sa.String(40), nullable=False, server_default="UNAVAILABLE"))
    op.add_column("fire_hotspots", sa.Column("provenance_metadata", sa.JSON(), nullable=False, server_default="{}"))
    op.create_index("ix_fire_hotspots_provider", "fire_hotspots", ["provider"])
    op.create_index("ix_fire_hotspots_source_record_id", "fire_hotspots", ["source_record_id"])
    op.create_index("ix_fire_hotspots_retrieved_at", "fire_hotspots", ["retrieved_at"])
    op.create_index("ix_fire_hotspots_satellite", "fire_hotspots", ["satellite"])
    op.create_index("ix_fire_hotspots_instrument", "fire_hotspots", ["instrument"])
    op.create_index("ix_fire_hotspots_quality_status", "fire_hotspots", ["quality_status"])
    op.create_index("ix_hotspots_provider_source_record", "fire_hotspots", ["provider", "source_record_id"])
    op.create_unique_constraint("uq_hotspots_provider_source_record", "fire_hotspots", ["provider", "source_record_id"])


def downgrade():
    op.drop_constraint("uq_hotspots_provider_source_record", "fire_hotspots", type_="unique")
    op.drop_index("ix_hotspots_provider_source_record", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_quality_status", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_instrument", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_satellite", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_retrieved_at", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_source_record_id", table_name="fire_hotspots")
    op.drop_index("ix_fire_hotspots_provider", table_name="fire_hotspots")
    op.drop_column("fire_hotspots", "provenance_metadata")
    op.drop_column("fire_hotspots", "quality_status")
    op.drop_column("fire_hotspots", "daynight")
    op.drop_column("fire_hotspots", "track")
    op.drop_column("fire_hotspots", "scan")
    op.drop_column("fire_hotspots", "frp")
    op.drop_column("fire_hotspots", "brightness")
    op.drop_column("fire_hotspots", "instrument")
    op.drop_column("fire_hotspots", "satellite")
    op.drop_column("fire_hotspots", "retrieved_at")
    op.drop_column("fire_hotspots", "source_record_id")
    op.drop_column("fire_hotspots", "provider")
