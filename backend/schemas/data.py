from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.data.sources import RefreshMode, SourceKind

STRICT_SCHEMA_CONFIG = ConfigDict(extra="forbid")


class DataSourceRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    name: str = Field(min_length=1, max_length=160)
    kind: SourceKind
    uri: str = Field(min_length=1, max_length=1000)
    expected_checksum: Optional[str] = Field(default=None, min_length=64, max_length=64)
    version: str = Field(default="v1", min_length=1, max_length=80)
    metadata: dict[str, str] = Field(default_factory=dict)
    refresh_mode: RefreshMode = RefreshMode.MANUAL
    schedule_cron: Optional[str] = Field(default=None, max_length=80)
    incremental_field: Optional[str] = Field(default=None, max_length=120)
    last_watermark: Optional[str] = Field(default=None, max_length=120)
    checkpoint_enabled: bool = True


class PipelineRunRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    dataset_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    dataset_version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    source: DataSourceRequest
    storage_format: Literal["csv", "geojson", "raster", "tif", "tiff", "jp2", "shapefile"]
    required_fields: list[str] = Field(default_factory=list)
    coordinate_fields: Optional[tuple[str, str]] = None
    label_field: Optional[str] = Field(default=None, max_length=120)
    expected_crs: Optional[str] = Field(default="EPSG:4326", max_length=80)
    baseline_statistics: dict[str, dict[str, float]] = Field(default_factory=dict)
    model_version_compatibility: list[str] = Field(default_factory=lambda: ["wildfire-risk-rf-v1", "wildfire-risk-xgb-v1"])
