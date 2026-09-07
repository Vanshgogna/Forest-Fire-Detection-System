from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="viewer", index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Region(TimestampMixin, Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    state: Mapped[str] = mapped_column(String(120), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    boundary_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    centroid_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ForestBoundary(TimestampMixin, Base):
    __tablename__ = "forest_boundaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    boundary_geojson: Mapped[dict] = mapped_column(JSON)
    area_hectares: Mapped[float | None] = mapped_column(Float, nullable=True)
    protection_status: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    region: Mapped[Region] = relationship()


class WeatherRecord(TimestampMixin, Base):
    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    temperature: Mapped[float] = mapped_column(Float)
    apparent_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float] = mapped_column(Float)
    wind_speed: Mapped[float] = mapped_column(Float)
    wind_direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_gusts: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall: Mapped[float] = mapped_column(Float)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    uv_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    fire_weather_index: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    source_type: Mapped[str] = mapped_column(String(120), default="unknown", index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    region: Mapped[Region] = relationship()

    __table_args__ = (Index("ix_weather_region_observed", "region_id", "observed_at"),)


class VegetationRecord(TimestampMixin, Base):
    __tablename__ = "vegetation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ndvi: Mapped[float] = mapped_column(Float)
    nbr: Mapped[float | None] = mapped_column(Float, nullable=True)
    vegetation_health_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    satellite_source: Mapped[str] = mapped_column(String(80), default="Sentinel-2")
    cloud_percentage: Mapped[float] = mapped_column(Float, default=0)
    provider: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    source_type: Mapped[str] = mapped_column(String(120), default="unknown", index=True)
    product_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    scene_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    processing_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="UNAVAILABLE", index=True)
    valid_pixel_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    region: Mapped[Region] = relationship()

    __table_args__ = (Index("ix_vegetation_region_captured", "region_id", "captured_at"),)


class SatelliteImage(TimestampMixin, Base):
    __tablename__ = "satellite_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    source: Mapped[str] = mapped_column(String(80), default="Sentinel-2", index=True)
    scene_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    product_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    product_level: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    processing_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    tile_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    cloud_percentage: Mapped[float] = mapped_column(Float, default=0)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="UNAVAILABLE", index=True)
    acquisition_status: Mapped[str] = mapped_column(String(40), default="DISCOVERED", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    region: Mapped[Region] = relationship()

    __table_args__ = (
        Index("ix_satellite_provider_product_id", "provider", "product_id"),
        Index("ix_satellite_region_captured", "region_id", "captured_at"),
        Index("ix_satellite_region_status", "region_id", "acquisition_status"),
        UniqueConstraint("provider", "product_id", name="uq_satellite_images_provider_product_id"),
    )


class FireHotspot(TimestampMixin, Base):
    __tablename__ = "fire_hotspots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(80), default="MODIS")
    provider: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    satellite: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    instrument: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    frp: Mapped[float | None] = mapped_column(Float, nullable=True)
    scan: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[float | None] = mapped_column(Float, nullable=True)
    daynight: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="UNAVAILABLE", index=True)
    provenance_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    region: Mapped[Region] = relationship()

    __table_args__ = (
        Index("ix_hotspots_region_detected", "region_id", "detected_at"),
        Index("ix_hotspots_provider_source_record", "provider", "source_record_id"),
        UniqueConstraint("provider", "source_record_id", name="uq_hotspots_provider_source_record"),
    )


class AIPrediction(TimestampMixin, Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    risk_category: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    feature_importance: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(80), index=True)
    region: Mapped[Region] = relationship()

    __table_args__ = (Index("ix_predictions_region_generated", "region_id", "generated_at"),)


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    title: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[str] = mapped_column(Text)
    recommended_actions: Mapped[list] = mapped_column(JSON)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[Region] = relationship()

    __table_args__ = (Index("ix_alerts_region_status", "region_id", "status"),)


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(50), index=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ActivityLog(TimestampMixin, Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(255), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class NotificationLog(TimestampMixin, Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(60), index=True)
    recipient: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(60), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    alert: Mapped[Alert | None] = relationship()


class ModelMetadata(TimestampMixin, Base):
    __tablename__ = "model_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(120))
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1_score: Mapped[float] = mapped_column(Float)
    feature_schema: Mapped[dict] = mapped_column(JSON)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalyticsSnapshot(TimestampMixin, Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_type: Mapped[str] = mapped_column(String(80), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, index=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    region: Mapped[Region | None] = relationship()


class SystemSetting(TimestampMixin, Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RefreshToken(TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_id", name="uq_refresh_tokens_token_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    token_id: Mapped[str] = mapped_column(String(120), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped[User | None] = relationship()
