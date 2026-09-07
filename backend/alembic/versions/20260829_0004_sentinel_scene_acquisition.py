"""sentinel scene acquisition

Revision ID: 20260829_0004
Revises: 20260829_0003
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_0004"
down_revision = "20260829_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("satellite_images", sa.Column("provider", sa.String(80), nullable=False, server_default="unknown"))
    op.add_column("satellite_images", sa.Column("product_id", sa.String(160), nullable=True))
    op.add_column("satellite_images", sa.Column("platform", sa.String(40), nullable=True))
    op.add_column("satellite_images", sa.Column("product_level", sa.String(40), nullable=True))
    op.add_column("satellite_images", sa.Column("processing_time", sa.DateTime(), nullable=True))
    op.add_column("satellite_images", sa.Column("retrieved_at", sa.DateTime(), nullable=True))
    op.add_column("satellite_images", sa.Column("storage_reference", sa.String(500), nullable=True))
    op.add_column("satellite_images", sa.Column("source_reference", sa.String(500), nullable=True))
    op.add_column("satellite_images", sa.Column("file_size_bytes", sa.Integer(), nullable=True))
    op.add_column("satellite_images", sa.Column("checksum", sa.String(128), nullable=True))
    op.add_column("satellite_images", sa.Column("quality_status", sa.String(40), nullable=False, server_default="UNAVAILABLE"))
    op.add_column("satellite_images", sa.Column("acquisition_status", sa.String(40), nullable=False, server_default="DISCOVERED"))
    op.create_index("ix_satellite_images_provider", "satellite_images", ["provider"])
    op.create_index("ix_satellite_images_product_id", "satellite_images", ["product_id"])
    op.create_index("ix_satellite_images_platform", "satellite_images", ["platform"])
    op.create_index("ix_satellite_images_product_level", "satellite_images", ["product_level"])
    op.create_index("ix_satellite_images_processing_time", "satellite_images", ["processing_time"])
    op.create_index("ix_satellite_images_retrieved_at", "satellite_images", ["retrieved_at"])
    op.create_index("ix_satellite_images_checksum", "satellite_images", ["checksum"])
    op.create_index("ix_satellite_images_quality_status", "satellite_images", ["quality_status"])
    op.create_index("ix_satellite_images_acquisition_status", "satellite_images", ["acquisition_status"])
    op.create_index("ix_satellite_provider_product_id", "satellite_images", ["provider", "product_id"])
    op.create_index("ix_satellite_region_captured", "satellite_images", ["region_id", "captured_at"])
    op.create_index("ix_satellite_region_status", "satellite_images", ["region_id", "acquisition_status"])
    op.create_unique_constraint("uq_satellite_images_provider_product_id", "satellite_images", ["provider", "product_id"])


def downgrade():
    op.drop_constraint("uq_satellite_images_provider_product_id", "satellite_images", type_="unique")
    op.drop_index("ix_satellite_region_status", table_name="satellite_images")
    op.drop_index("ix_satellite_region_captured", table_name="satellite_images")
    op.drop_index("ix_satellite_provider_product_id", table_name="satellite_images")
    op.drop_index("ix_satellite_images_acquisition_status", table_name="satellite_images")
    op.drop_index("ix_satellite_images_quality_status", table_name="satellite_images")
    op.drop_index("ix_satellite_images_checksum", table_name="satellite_images")
    op.drop_index("ix_satellite_images_retrieved_at", table_name="satellite_images")
    op.drop_index("ix_satellite_images_processing_time", table_name="satellite_images")
    op.drop_index("ix_satellite_images_product_level", table_name="satellite_images")
    op.drop_index("ix_satellite_images_platform", table_name="satellite_images")
    op.drop_index("ix_satellite_images_product_id", table_name="satellite_images")
    op.drop_index("ix_satellite_images_provider", table_name="satellite_images")
    op.drop_column("satellite_images", "acquisition_status")
    op.drop_column("satellite_images", "quality_status")
    op.drop_column("satellite_images", "checksum")
    op.drop_column("satellite_images", "file_size_bytes")
    op.drop_column("satellite_images", "source_reference")
    op.drop_column("satellite_images", "storage_reference")
    op.drop_column("satellite_images", "retrieved_at")
    op.drop_column("satellite_images", "processing_time")
    op.drop_column("satellite_images", "product_level")
    op.drop_column("satellite_images", "platform")
    op.drop_column("satellite_images", "product_id")
    op.drop_column("satellite_images", "provider")
