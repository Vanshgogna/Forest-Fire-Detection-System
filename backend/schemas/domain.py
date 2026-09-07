from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskCategory = Literal["Low", "Moderate", "High", "Critical"]
AlertStatus = Literal["new", "acknowledged", "resolved"]
STRICT_SCHEMA_CONFIG = ConfigDict(extra="forbid")


class RegionCreate(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    name: str
    state: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary_geojson: Optional[dict] = None


class RegionRead(RegionCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class WeatherRecordCreate(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    region_id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_at: datetime
    retrieved_at: datetime
    temperature: float
    apparent_temperature: Optional[float] = None
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0)
    wind_direction: Optional[float] = Field(default=None, ge=0, le=360)
    wind_gusts: Optional[float] = Field(default=None, ge=0)
    rainfall: float = Field(ge=0)
    precipitation: Optional[float] = Field(default=None, ge=0)
    pressure: Optional[float] = None
    cloud_cover: Optional[float] = Field(default=None, ge=0, le=100)
    uv_index: Optional[float] = Field(default=None, ge=0)
    provider: str = Field(min_length=1, max_length=80)
    source_type: str = Field(min_length=1, max_length=120)
    source_url: Optional[str] = Field(default=None, max_length=500)
    quality_flags: list[str] = Field(default_factory=list)


class FireWeatherIndexRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    temperature: float = Field(ge=-60, le=70)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=160)
    rainfall: float = Field(ge=0, le=500)
    pressure: Optional[float] = Field(default=None, ge=800, le=1100)
    cloud_cover: Optional[float] = Field(default=None, ge=0, le=100)
    uv_index: Optional[float] = Field(default=None, ge=0, le=15)


class SatelliteMetadata(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    source: str = "Sentinel-2"
    scene_id: Optional[str] = None
    cloud_percentage: float = Field(default=0, ge=0, le=100)
    spatial_resolution_meters: Optional[float] = None
    processing_level: Optional[str] = None


class VegetationIndexRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    nir: float = Field(ge=-1, le=1)
    red: float = Field(ge=-1, le=1)
    swir: float = Field(ge=-1, le=1)
    cloud_percentage: float = Field(default=0, ge=0, le=100)


class SatelliteScenePlanRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    scene_id: str = Field(min_length=1, max_length=160)
    source: Literal["Sentinel-2", "MODIS", "VIIRS"] = "Sentinel-2"
    acquisition_date: str = Field(default="not-specified", min_length=1, max_length=40)
    crs: str = Field(default="EPSG:4326", min_length=3, max_length=40)
    cloud_percentage: float = Field(default=0, ge=0, le=100)
    storage_uri: Optional[str] = Field(default=None, max_length=500)
    bounds: Optional[dict] = None


class PredictionJobRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    region_ids: Optional[list[int]] = None
    run_async: bool = False
    include_explainability: bool = True


class PredictionRead(BaseModel):
    id: int
    region_id: int
    generated_at: datetime
    risk_score: float
    risk_category: RiskCategory
    confidence: float
    feature_importance: dict
    explanation: str
    model_version: str
    model_config = ConfigDict(from_attributes=True)


class AlertUpdate(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    status: AlertStatus
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None


class ModelTrainingRequest(BaseModel):
    model_config = STRICT_SCHEMA_CONFIG

    algorithm: str = Field(default="random_forest", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    target_column: str = "risk_class"
    tune_hyperparameters: bool = False
    persist_model: bool = True
