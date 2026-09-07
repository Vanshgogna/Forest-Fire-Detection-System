"""weather provenance fields

Revision ID: 20260829_0002
Revises: 20260726_0001
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_0002"
down_revision = "20260726_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("weather_records", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("retrieved_at", sa.DateTime(), nullable=True))
    op.add_column("weather_records", sa.Column("apparent_temperature", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("wind_direction", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("wind_gusts", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("precipitation", sa.Float(), nullable=True))
    op.add_column("weather_records", sa.Column("provider", sa.String(80), nullable=False, server_default="unknown"))
    op.add_column("weather_records", sa.Column("source_type", sa.String(120), nullable=False, server_default="unknown"))
    op.add_column("weather_records", sa.Column("source_url", sa.String(500), nullable=True))
    op.add_column("weather_records", sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_weather_records_retrieved_at", "weather_records", ["retrieved_at"])
    op.create_index("ix_weather_records_provider", "weather_records", ["provider"])
    op.create_index("ix_weather_records_source_type", "weather_records", ["source_type"])


def downgrade():
    op.drop_index("ix_weather_records_source_type", table_name="weather_records")
    op.drop_index("ix_weather_records_provider", table_name="weather_records")
    op.drop_index("ix_weather_records_retrieved_at", table_name="weather_records")
    op.drop_column("weather_records", "quality_flags")
    op.drop_column("weather_records", "source_url")
    op.drop_column("weather_records", "source_type")
    op.drop_column("weather_records", "provider")
    op.drop_column("weather_records", "precipitation")
    op.drop_column("weather_records", "wind_gusts")
    op.drop_column("weather_records", "wind_direction")
    op.drop_column("weather_records", "apparent_temperature")
    op.drop_column("weather_records", "retrieved_at")
    op.drop_column("weather_records", "longitude")
    op.drop_column("weather_records", "latitude")
