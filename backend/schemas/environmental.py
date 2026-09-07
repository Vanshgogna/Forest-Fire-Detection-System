from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.services.environmental_foundation import DataQualityStatus


class MissingEnvironmentalData(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    available: Literal[False] = False
    status: DataQualityStatus
    reason: str
    values: None = None


class CanonicalWeatherData(BaseModel):
    temperature: float
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0)
    precipitation: float = Field(ge=0)
    fire_weather_index: float
    observed_at: str
    retrieved_at: str
    units: dict[str, str]


class CanonicalVegetationData(BaseModel):
    available: Literal[True] = True
    status: DataQualityStatus
    provider: str
    source_type: str
    ndvi_mean: float = Field(ge=-1, le=1)
    ndvi_median: float | None = Field(default=None, ge=-1, le=1)
    ndvi_min: float | None = Field(default=None, ge=-1, le=1)
    ndvi_max: float | None = Field(default=None, ge=-1, le=1)
    nbr_mean: float | None = Field(default=None, ge=-1, le=1)
    nbr_median: float | None = Field(default=None, ge=-1, le=1)
    nbr_min: float | None = Field(default=None, ge=-1, le=1)
    nbr_max: float | None = Field(default=None, ge=-1, le=1)
    nbr_valid_pixel_percentage: float | None = Field(default=None, ge=0, le=100)
    valid_pixel_percentage: float | None = Field(default=None, ge=0, le=100)
    captured_at: str
    processed_at: str | None = None
    scene_id: str | None = None
    product_id: str | None = None
    values: dict[str, Any]


class HotspotDetection(BaseModel):
    id: int | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    detected_at: str
    retrieved_at: str | None = None
    satellite: str | None = None
    instrument: str | None = None
    confidence: float = Field(ge=0, le=100)
    severity: str
    frp: float | None = None
    brightness: float | None = None
    source_record_id: str | None = None


class CanonicalHotspotData(BaseModel):
    available: Literal[True] = True
    status: DataQualityStatus
    provider: str
    source_type: str
    hotspot_count_24h: int = Field(ge=0)
    hotspot_count_48h: int = Field(ge=0)
    hotspot_count_7d: int = Field(ge=0)
    hotspot_density: float | None = None
    nearest_hotspot_distance_km: float | None = None
    latest_detection_at: str | None = None
    retrieved_at: str | None = None
    records: list[HotspotDetection] = Field(default_factory=list)
    attribution: str = "NASA FIRMS"
    values: dict[str, Any]


class EnvironmentalSnapshot(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    region_id: str
    timestamp: datetime
    data_mode: str
    region: dict[str, Any]
    weather: CanonicalWeatherData | MissingEnvironmentalData
    vegetation: CanonicalVegetationData | MissingEnvironmentalData
    hotspots: CanonicalHotspotData | MissingEnvironmentalData
    provenance: dict[str, dict[str, Any] | None]
    quality: dict[str, DataQualityStatus]
    availability: dict[str, bool]
