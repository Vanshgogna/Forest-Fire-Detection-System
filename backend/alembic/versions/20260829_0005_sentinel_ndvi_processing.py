"""sentinel ndvi processing provenance

Revision ID: 20260829_0005
Revises: 20260829_0004
Create Date: 2026-08-29 19:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260829_0005"
down_revision = "20260829_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("vegetation_records", "nbr", existing_type=sa.Float(), nullable=True)
    op.alter_column("vegetation_records", "vegetation_health_index", existing_type=sa.Float(), nullable=True)
    op.add_column("vegetation_records", sa.Column("provider", sa.String(length=80), nullable=False, server_default="unknown"))
    op.add_column("vegetation_records", sa.Column("source_type", sa.String(length=120), nullable=False, server_default="unknown"))
    op.add_column("vegetation_records", sa.Column("product_id", sa.String(length=160), nullable=True))
    op.add_column("vegetation_records", sa.Column("scene_id", sa.String(length=160), nullable=True))
    op.add_column("vegetation_records", sa.Column("processing_version", sa.String(length=80), nullable=True))
    op.add_column("vegetation_records", sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.add_column("vegetation_records", sa.Column("quality_status", sa.String(length=40), nullable=False, server_default="UNAVAILABLE"))
    op.add_column("vegetation_records", sa.Column("valid_pixel_percentage", sa.Float(), nullable=True))
    op.add_column("vegetation_records", sa.Column("provenance_metadata", sa.JSON(), nullable=False, server_default="{}"))
    op.create_index("ix_vegetation_records_provider", "vegetation_records", ["provider"])
    op.create_index("ix_vegetation_records_source_type", "vegetation_records", ["source_type"])
    op.create_index("ix_vegetation_records_product_id", "vegetation_records", ["product_id"])
    op.create_index("ix_vegetation_records_scene_id", "vegetation_records", ["scene_id"])
    op.create_index("ix_vegetation_records_processing_version", "vegetation_records", ["processing_version"])
    op.create_index("ix_vegetation_records_processed_at", "vegetation_records", ["processed_at"])
    op.create_index("ix_vegetation_records_quality_status", "vegetation_records", ["quality_status"])
    op.alter_column("vegetation_records", "provider", server_default=None)
    op.alter_column("vegetation_records", "source_type", server_default=None)
    op.alter_column("vegetation_records", "quality_status", server_default=None)
    op.alter_column("vegetation_records", "provenance_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_vegetation_records_quality_status", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_processed_at", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_processing_version", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_scene_id", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_product_id", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_source_type", table_name="vegetation_records")
    op.drop_index("ix_vegetation_records_provider", table_name="vegetation_records")
    op.drop_column("vegetation_records", "provenance_metadata")
    op.drop_column("vegetation_records", "valid_pixel_percentage")
    op.drop_column("vegetation_records", "quality_status")
    op.drop_column("vegetation_records", "processed_at")
    op.drop_column("vegetation_records", "processing_version")
    op.drop_column("vegetation_records", "scene_id")
    op.drop_column("vegetation_records", "product_id")
    op.drop_column("vegetation_records", "source_type")
    op.drop_column("vegetation_records", "provider")
    op.alter_column("vegetation_records", "vegetation_health_index", existing_type=sa.Float(), nullable=False)
    op.alter_column("vegetation_records", "nbr", existing_type=sa.Float(), nullable=False)
