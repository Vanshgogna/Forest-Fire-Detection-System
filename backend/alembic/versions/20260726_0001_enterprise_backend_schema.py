"""enterprise backend schema

Revision ID: 20260726_0001
Revises:
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260726_0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamp_columns():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def create_timestamp_indexes(table_name: str):
    op.create_index(f"ix_{table_name}_created_at", table_name, ["created_at"])
    op.create_index(f"ix_{table_name}_updated_at", table_name, ["updated_at"])


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    create_timestamp_indexes("users")

    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("boundary_geojson", sa.JSON(), nullable=True),
        sa.Column("centroid_geojson", sa.JSON(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index("ix_regions_name", "regions", ["name"])
    op.create_index("ix_regions_state", "regions", ["state"])
    create_timestamp_indexes("regions")

    op.create_table(
        "forest_boundaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("boundary_geojson", sa.JSON(), nullable=False),
        sa.Column("area_hectares", sa.Float(), nullable=True),
        sa.Column("protection_status", sa.String(120), nullable=True),
        *timestamp_columns(),
    )
    op.create_index("ix_forest_boundaries_region_id", "forest_boundaries", ["region_id"])
    create_timestamp_indexes("forest_boundaries")

    op.create_table(
        "weather_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=False),
        sa.Column("rainfall", sa.Float(), nullable=False),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("uv_index", sa.Float(), nullable=True),
        sa.Column("fire_weather_index", sa.Float(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_weather_region_observed", "weather_records", ["region_id", "observed_at"])
    create_timestamp_indexes("weather_records")

    op.create_table(
        "vegetation_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("ndvi", sa.Float(), nullable=False),
        sa.Column("nbr", sa.Float(), nullable=False),
        sa.Column("vegetation_health_index", sa.Float(), nullable=False),
        sa.Column("satellite_source", sa.String(80), nullable=False),
        sa.Column("cloud_percentage", sa.Float(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_vegetation_region_captured", "vegetation_records", ["region_id", "captured_at"])
    create_timestamp_indexes("vegetation_records")

    op.create_table(
        "satellite_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("scene_id", sa.String(160), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("tile_id", sa.String(120), nullable=True),
        sa.Column("cloud_percentage", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_satellite_images_region_id", "satellite_images", ["region_id"])
    op.create_index("ix_satellite_images_scene_id", "satellite_images", ["scene_id"])
    create_timestamp_indexes("satellite_images")

    op.create_table(
        "fire_hotspots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(40), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_hotspots_region_detected", "fire_hotspots", ["region_id", "detected_at"])
    create_timestamp_indexes("fire_hotspots")

    op.create_table(
        "ai_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_category", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("feature_importance", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_predictions_region_generated", "ai_predictions", ["region_id", "generated_at"])
    create_timestamp_indexes("ai_predictions")

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("severity", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_actions", sa.JSON(), nullable=False),
        sa.Column("acknowledged_by", sa.String(255), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index("ix_alerts_region_status", "alerts", ["region_id", "status"])
    create_timestamp_indexes("alerts")

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_reports_report_type", "reports", ["report_type"])
    create_timestamp_indexes("reports")

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_activity_logs_actor", "activity_logs", ["actor"])
    op.create_index("ix_activity_logs_action", "activity_logs", ["action"])
    op.create_index("ix_activity_logs_resource", "activity_logs", ["resource_type", "resource_id"])
    create_timestamp_indexes("activity_logs")

    op.create_table(
        "model_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("algorithm", sa.String(120), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("precision", sa.Float(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("f1_score", sa.Float(), nullable=False),
        sa.Column("feature_schema", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(500), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("trained_at", sa.DateTime(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_model_metadata_version", "model_metadata", ["version"], unique=True)
    op.create_index("ix_model_metadata_is_active", "model_metadata", ["is_active"])
    create_timestamp_indexes("model_metadata")

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("channel", sa.String(60), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_notification_logs_alert_id", "notification_logs", ["alert_id"])
    op.create_index("ix_notification_logs_channel", "notification_logs", ["channel"])
    op.create_index("ix_notification_logs_recipient", "notification_logs", ["recipient"])
    op.create_index("ix_notification_logs_status", "notification_logs", ["status"])
    create_timestamp_indexes("notification_logs")

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_type", sa.String(80), nullable=False),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_analytics_snapshots_snapshot_type", "analytics_snapshots", ["snapshot_type"])
    op.create_index("ix_analytics_snapshots_region_id", "analytics_snapshots", ["region_id"])
    op.create_index("ix_analytics_snapshots_period", "analytics_snapshots", ["period_start", "period_end"])
    create_timestamp_indexes("analytics_snapshots")

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)
    create_timestamp_indexes("system_settings")

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("token_id", sa.String(120), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_id", name="uq_refresh_tokens_token_id"),
        *timestamp_columns(),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_id", "refresh_tokens", ["token_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    create_timestamp_indexes("refresh_tokens")


def downgrade():
    for table_name in [
        "refresh_tokens",
        "system_settings",
        "analytics_snapshots",
        "notification_logs",
        "model_metadata",
        "activity_logs",
        "reports",
        "alerts",
        "ai_predictions",
        "fire_hotspots",
        "satellite_images",
        "vegetation_records",
        "weather_records",
        "forest_boundaries",
        "regions",
        "users",
    ]:
        op.drop_table(table_name)
