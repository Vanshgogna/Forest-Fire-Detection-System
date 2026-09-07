from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-jwt-key-do-not-use-in-production"
DEVELOPMENT_DEMO_PASSWORD = "development-demo-password-change-me"
PRODUCTION_ENVIRONMENTS = {"production", "staging"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore", enable_decoding=False)

    app_name: str = Field(default="FireSight AI Environmental Intelligence API", alias="APP_NAME")
    api_version: str = Field(default="v1", alias="API_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="PORT")

    database_url: str = Field(default="postgresql+psycopg://firesight:firesight@localhost:5432/firesight", alias="DATABASE_URL")
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")
    database_pool_recycle_seconds: int = Field(default=1800, alias="DATABASE_POOL_RECYCLE_SECONDS")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    jwt_secret_key: str = Field(default=DEVELOPMENT_JWT_SECRET, alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_minutes: int = Field(default=60, alias="ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=14, alias="REFRESH_TOKEN_DAYS")
    demo_login_enabled: bool = Field(default=True, alias="DEMO_LOGIN_ENABLED")
    demo_login_email: str = Field(default="officer@firesight.ai", alias="DEMO_LOGIN_EMAIL")
    demo_login_password: str = Field(default=DEVELOPMENT_DEMO_PASSWORD, alias="DEMO_LOGIN_PASSWORD")

    dataset_dir: str = Field(default="datasets", alias="DATASET_DIR")
    model_artifact_dir: str = Field(default="backend/artifacts/models", alias="MODEL_ARTIFACT_DIR")
    upload_dir: str = Field(default="backend/artifacts/uploads", alias="UPLOAD_DIR")
    raster_artifact_dir: str = Field(default="backend/artifacts/rasters", alias="RASTER_ARTIFACT_DIR")
    cache_artifact_dir: str = Field(default="backend/artifacts/cache", alias="CACHE_ARTIFACT_DIR")
    report_artifact_dir: str = Field(default="backend/artifacts/reports", alias="REPORT_ARTIFACT_DIR")
    data_archive_dir: str = Field(default="backend/artifacts/data-archive", alias="DATA_ARCHIVE_DIR")
    data_checkpoint_dir: str = Field(default="backend/artifacts/data-checkpoints", alias="DATA_CHECKPOINT_DIR")

    weather_api_base_url: str = Field(default="https://api.open-meteo.com/v1", alias="WEATHER_API_BASE_URL")
    weather_api_key: Optional[str] = Field(default=None, alias="WEATHER_API_KEY")
    copernicus_client_id: Optional[str] = Field(default=None, alias="COPERNICUS_CLIENT_ID")
    copernicus_client_secret: Optional[str] = Field(default=None, alias="COPERNICUS_CLIENT_SECRET")
    copernicus_token_url: str = Field(
        default="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        alias="COPERNICUS_TOKEN_URL",
    )
    sentinel_enabled: bool = Field(default=False, alias="SENTINEL_ENABLED")
    sentinel_base_url: str = Field(default="https://catalogue.dataspace.copernicus.eu/odata/v1", alias="SENTINEL_BASE_URL")
    sentinel_catalog_url: Optional[str] = Field(default=None, alias="SENTINEL_CATALOG_URL")
    sentinel_download_url: str = Field(default="https://download.dataspace.copernicus.eu/odata/v1", alias="SENTINEL_DOWNLOAD_URL")
    sentinel_product_type: str = Field(default="S2MSI2A", alias="SENTINEL_PRODUCT_TYPE")
    sentinel_lookback_days: int = Field(default=14, alias="SENTINEL_LOOKBACK_DAYS")
    sentinel_max_cloud_cover: float = Field(default=40.0, alias="SENTINEL_MAX_CLOUD_COVER")
    sentinel_request_timeout: float = Field(default=30.0, alias="SENTINEL_REQUEST_TIMEOUT")
    sentinel_max_scene_size_mb: float = Field(default=512.0, alias="SENTINEL_MAX_SCENE_SIZE_MB")
    sentinel_temp_dir: str = Field(default="backend/artifacts/rasters/tmp/sentinel", alias="SENTINEL_TEMP_DIR")
    sentinel_retry_attempts: int = Field(default=2, alias="SENTINEL_RETRY_ATTEMPTS")
    sentinel_retry_backoff_seconds: float = Field(default=1.0, alias="SENTINEL_RETRY_BACKOFF_SECONDS")
    sentinel_refresh_interval_hours: int = Field(default=24, alias="SENTINEL_REFRESH_INTERVAL_HOURS")
    sentinel_analysis_resolution: float = Field(default=20.0, alias="SENTINEL_ANALYSIS_RESOLUTION")
    sentinel_raster_max_memory_mb: float = Field(default=256.0, alias="SENTINEL_RASTER_MAX_MEMORY_MB")
    sentinel_processing_dir: str = Field(default="backend/artifacts/rasters/processed/sentinel", alias="SENTINEL_PROCESSING_DIR")
    sentinel_min_valid_pixel_percent: float = Field(default=40.0, alias="SENTINEL_MIN_VALID_PIXEL_PERCENT")
    sentinel_quality_mask_version: str = Field(default="6D-2-v1", alias="SENTINEL_QUALITY_MASK_VERSION")
    sentinel_ndvi_processing_version: str = Field(default="6D-3-v1", alias="SENTINEL_NDVI_PROCESSING_VERSION")
    modis_hotspot_url: Optional[str] = Field(default=None, alias="MODIS_HOTSPOT_URL")
    viirs_hotspot_url: Optional[str] = Field(default=None, alias="VIIRS_HOTSPOT_URL")
    firms_map_key: Optional[str] = Field(default=None, alias="FIRMS_MAP_KEY")
    firms_base_url: str = Field(default="https://firms.modaps.eosdis.nasa.gov/api", alias="FIRMS_BASE_URL")
    firms_enabled: bool = Field(default=False, alias="FIRMS_ENABLED")
    firms_product: str = Field(default="VIIRS_SNPP_NRT", alias="FIRMS_PRODUCT")
    firms_lookback_hours: int = Field(default=24, alias="FIRMS_LOOKBACK_HOURS")
    firms_max_records: int = Field(default=500, alias="FIRMS_MAX_RECORDS")
    firms_request_timeout: float = Field(default=10.0, alias="FIRMS_REQUEST_TIMEOUT")
    firms_region_buffer_degrees: float = Field(default=0.5, alias="FIRMS_REGION_BUFFER_DEGREES")
    firms_retry_attempts: int = Field(default=2, alias="FIRMS_RETRY_ATTEMPTS")
    firms_retry_backoff_seconds: float = Field(default=0.5, alias="FIRMS_RETRY_BACKOFF_SECONDS")
    firms_refresh_interval_minutes: int = Field(default=180, alias="FIRMS_REFRESH_INTERVAL_MINUTES")
    cloudinary_url: Optional[str] = Field(default=None, alias="CLOUDINARY_URL")

    data_mode: Literal["live", "simulation"] = Field(default="live", alias="DATA_MODE")
    critical_risk_threshold: int = Field(default=85, alias="CRITICAL_RISK_THRESHOLD")
    high_risk_threshold: int = Field(default=70, alias="HIGH_RISK_THRESHOLD")
    rate_limit_per_minute: int = Field(default=180, alias="RATE_LIMIT_PER_MINUTE")
    max_request_body_bytes: int = Field(default=1_048_576, alias="MAX_REQUEST_BODY_BYTES")
    replay_window_seconds: int = Field(default=300, alias="REPLAY_WINDOW_SECONDS")
    default_page_size: int = Field(default=100, alias="DEFAULT_PAGE_SIZE")
    max_page_size: int = Field(default=500, alias="MAX_PAGE_SIZE")
    weather_cache_seconds: int = Field(default=300, alias="WEATHER_CACHE_SECONDS")
    weather_request_timeout: float = Field(default=8.0, alias="WEATHER_REQUEST_TIMEOUT")
    weather_recent_minutes: int = Field(default=30, alias="WEATHER_RECENT_MINUTES")
    weather_stale_minutes: int = Field(default=120, alias="WEATHER_STALE_MINUTES")
    vegetation_max_age_days: int = Field(default=5, alias="VEGETATION_MAX_AGE_DAYS")
    hotspot_max_age_hours: int = Field(default=24, alias="HOTSPOT_MAX_AGE_HOURS")
    weather_temperature_difference_warning_c: float = Field(default=3.0, alias="WEATHER_TEMPERATURE_DIFFERENCE_WARNING_C")
    weather_temperature_difference_investigate_c: float = Field(default=6.0, alias="WEATHER_TEMPERATURE_DIFFERENCE_INVESTIGATE_C")
    weather_humidity_difference_warning_percent: float = Field(default=15.0, alias="WEATHER_HUMIDITY_DIFFERENCE_WARNING_PERCENT")
    weather_humidity_difference_investigate_percent: float = Field(default=30.0, alias="WEATHER_HUMIDITY_DIFFERENCE_INVESTIGATE_PERCENT")
    weather_wind_difference_warning_kmh: float = Field(default=10.0, alias="WEATHER_WIND_DIFFERENCE_WARNING_KMH")
    weather_wind_difference_investigate_kmh: float = Field(default=20.0, alias="WEATHER_WIND_DIFFERENCE_INVESTIGATE_KMH")
    weather_rainfall_difference_warning_mm: float = Field(default=2.0, alias="WEATHER_RAINFALL_DIFFERENCE_WARNING_MM")
    weather_rainfall_difference_investigate_mm: float = Field(default=8.0, alias="WEATHER_RAINFALL_DIFFERENCE_INVESTIGATE_MM")
    prediction_batch_size_limit: int = Field(default=500, alias="PREDICTION_BATCH_SIZE_LIMIT")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
        alias="CORS_ORIGINS",
    )

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://") and "+psycopg" not in value.split("://", maxsplit=1)[0]:
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.environment in PRODUCTION_ENVIRONMENTS:
            if self.jwt_secret_key == DEVELOPMENT_JWT_SECRET or len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be replaced with a long secret in production")
            if self.demo_login_enabled and (self.demo_login_password == DEVELOPMENT_DEMO_PASSWORD or len(self.demo_login_password) < 12):
                raise ValueError("DEMO_LOGIN_PASSWORD must be replaced with a strong value or DEMO_LOGIN_ENABLED=false in production")
            if "localhost" in self.database_url or "firesight:firesight" in self.database_url:
                raise ValueError("DATABASE_URL must point to a managed production database")
            local_cors = any(origin == "*" or "localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins)
            if not self.cors_origins or local_cors:
                raise ValueError("CORS_ORIGINS must contain production frontend origins")
            if self.data_mode != "live":
                raise ValueError("DATA_MODE must be live in production")
        return self

    def artifact_directories(self) -> dict[str, str]:
        """Return configured local storage directories used by workers and APIs."""
        return {
            "datasets": self.dataset_dir,
            "models": self.model_artifact_dir,
            "uploads": self.upload_dir,
            "rasters": self.raster_artifact_dir,
            "cache": self.cache_artifact_dir,
            "reports": self.report_artifact_dir,
            "data_archive": self.data_archive_dir,
            "data_checkpoints": self.data_checkpoint_dir,
        }

    def ensure_artifact_directories(self) -> None:
        """Create configured local artifact directories for development and Docker deployments."""
        for directory in self.artifact_directories().values():
            Path(directory).mkdir(parents=True, exist_ok=True)

    def public_config(self) -> dict[str, Any]:
        """Return a redacted configuration summary for readiness and admin diagnostics."""
        return {
            "app_name": self.app_name,
            "api_version": self.api_version,
            "environment": self.environment,
            "database_configured": bool(self.database_url),
            "redis_configured": bool(self.redis_url),
            "weather_api_configured": bool(self.weather_api_key or self.weather_api_base_url),
            "satellite_catalog_configured": bool((self.sentinel_enabled and (self.sentinel_catalog_url or self.sentinel_base_url)) or self.modis_hotspot_url or self.viirs_hotspot_url),
            "firms_configured": bool(self.firms_enabled and self.firms_map_key),
            "firms": {
                "enabled": self.firms_enabled,
                "base_url": self.firms_base_url,
                "product": self.firms_product,
                "lookback_hours": self.firms_lookback_hours,
                "max_records": self.firms_max_records,
                "request_timeout": self.firms_request_timeout,
                "region_buffer_degrees": self.firms_region_buffer_degrees,
                "refresh_interval_minutes": self.firms_refresh_interval_minutes,
                "map_key_configured": bool(self.firms_map_key),
            },
            "sentinel": {
                "enabled": self.sentinel_enabled,
                "base_url": self.sentinel_catalog_url or self.sentinel_base_url,
                "download_url": self.sentinel_download_url,
                "product_type": self.sentinel_product_type,
                "lookback_days": self.sentinel_lookback_days,
                "max_cloud_cover": self.sentinel_max_cloud_cover,
                "request_timeout": self.sentinel_request_timeout,
                "max_scene_size_mb": self.sentinel_max_scene_size_mb,
                "temp_dir": self.sentinel_temp_dir,
                "retry_attempts": self.sentinel_retry_attempts,
                "retry_backoff_seconds": self.sentinel_retry_backoff_seconds,
                "refresh_interval_hours": self.sentinel_refresh_interval_hours,
                "analysis_resolution": self.sentinel_analysis_resolution,
                "raster_max_memory_mb": self.sentinel_raster_max_memory_mb,
                "processing_dir": self.sentinel_processing_dir,
                "min_valid_pixel_percent": self.sentinel_min_valid_pixel_percent,
                "quality_mask_version": self.sentinel_quality_mask_version,
                "ndvi_processing_version": self.sentinel_ndvi_processing_version,
                "client_id_configured": bool(self.copernicus_client_id),
                "client_secret_configured": bool(self.copernicus_client_secret),
            },
            "cloudinary_configured": bool(self.cloudinary_url),
            "data_mode": self.data_mode,
            "demo_login_enabled": self.demo_login_enabled,
            "cors_origins": self.cors_origins,
            "artifact_directories": self.artifact_directories(),
            "performance": {
                "database_pool_size": self.database_pool_size,
                "default_page_size": self.default_page_size,
                "max_page_size": self.max_page_size,
                "weather_cache_seconds": self.weather_cache_seconds,
                "weather_recent_minutes": self.weather_recent_minutes,
                "weather_stale_minutes": self.weather_stale_minutes,
                "vegetation_max_age_days": self.vegetation_max_age_days,
                "hotspot_max_age_hours": self.hotspot_max_age_hours,
                "prediction_batch_size_limit": self.prediction_batch_size_limit,
            },
            "security": {
                "rate_limit_per_minute": self.rate_limit_per_minute,
                "max_request_body_bytes": self.max_request_body_bytes,
                "replay_window_seconds": self.replay_window_seconds,
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
