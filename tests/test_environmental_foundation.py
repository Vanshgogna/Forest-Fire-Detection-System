from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.schemas.environmental import CanonicalWeatherData, MissingEnvironmentalData
from backend.services.environmental_data_service import EnvironmentalDataService
from backend.services.environmental_foundation import (
    CANONICAL_UNITS,
    DataMode,
    DataProvenance,
    DataQualityStatus,
    FreshnessPolicy,
    ProviderErrorKind,
    ProviderName,
    ProviderType,
    classify_freshness,
    classify_provider_error,
    ensure_aware_utc,
    validate_canonical_units,
    validate_measurement_ranges,
)
from backend.services.region_registry import get_region_location
from test_sentinel_quality_masking import _session


class TimeoutExample(Exception):
    pass


class FakeWeatherProvider:
    provider = ProviderName.OPEN_METEO.value

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[str] = []

    def weather_for_region(self, region_id: str, forecast_days: int = 3):
        self.calls.append(region_id)
        return self.payload


def weather_payload(status: DataQualityStatus = DataQualityStatus.LIVE) -> dict:
    observed_at = "2026-08-29T11:30"
    provenance_observed_at = "2026-08-29T11:30:00+05:30"
    retrieved_at = "2026-08-29T06:05:00+00:00"
    return {
        "status": "ok",
        "data_status": status.value,
        "provider": "open-meteo",
        "provider_type": ProviderType.WEATHER.value,
        "source_type": "forecast_model_current_conditions",
        "source": "https://api.open-meteo.com/v1/forecast",
        "location": get_region_location("r1").as_dict(),
        "units": CANONICAL_UNITS,
        "current": {
            "temperature": 26.5,
            "humidity": 55.0,
            "wind_speed": 22.8,
            "precipitation": 0.0,
            "rainfall": 0.0,
            "fire_weather_risk_index": 50.63,
            "observed_at": observed_at,
            "retrieved_at": retrieved_at,
        },
        "retrieved_at": retrieved_at,
        "cache": {"status": "miss", "age_seconds": 0, "ttl_seconds": 300},
        "provenance": {
            "provider": "open-meteo",
            "provider_type": ProviderType.WEATHER.value,
            "source_type": "forecast_model_current_conditions",
            "source_record_id": None,
            "source_url": "https://api.open-meteo.com/v1/forecast",
            "observed_at": provenance_observed_at,
            "acquired_at": None,
            "retrieved_at": retrieved_at,
            "request_id": None,
            "region_id": "r1",
            "quality_status": status.value,
        },
    }


def test_data_quality_status_and_freshness_handling():
    retrieved = datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc)

    assert classify_freshness(retrieved - timedelta(minutes=5), retrieved, timedelta(hours=2), timedelta(minutes=30)) == DataQualityStatus.LIVE
    assert classify_freshness(retrieved - timedelta(minutes=45), retrieved, timedelta(hours=2), timedelta(minutes=30)) == DataQualityStatus.RECENT
    assert classify_freshness(retrieved - timedelta(minutes=5), retrieved, timedelta(hours=2), timedelta(minutes=30), cache_hit=True) == DataQualityStatus.CACHED
    assert classify_freshness(retrieved - timedelta(hours=3), retrieved, timedelta(hours=2), timedelta(minutes=30)) == DataQualityStatus.STALE
    assert classify_freshness(None, retrieved, timedelta(hours=2)) == DataQualityStatus.SUSPICIOUS
    assert classify_freshness(retrieved, retrieved, timedelta(hours=2), unavailable=True) == DataQualityStatus.UNAVAILABLE
    assert classify_freshness(retrieved, retrieved, timedelta(hours=2), simulated=True) == DataQualityStatus.SIMULATED


def test_provenance_creation_preserves_observation_and_retrieval_time():
    observed = datetime(2026, 8, 27, 5, 30, tzinfo=timezone.utc)
    retrieved = datetime(2026, 8, 29, 5, 40, tzinfo=timezone.utc)
    provenance = DataProvenance(
        provider=ProviderName.OPEN_METEO.value,
        provider_type=ProviderType.WEATHER,
        source_type="forecast_model_current_conditions",
        region_id="r1",
        observed_at=observed,
        retrieved_at=retrieved,
        quality_status=DataQualityStatus.STALE,
    ).to_dict()

    assert provenance["observed_at"] != provenance["retrieved_at"]
    assert provenance["quality_status"] == "STALE"
    assert provenance["provider_type"] == "WEATHER"


def test_region_resolution_and_unit_validation():
    region = get_region_location("r1")

    assert region.name == "Bandipur Tiger Reserve"
    assert region.coordinates == (11.667, 76.629)
    assert validate_canonical_units({"temperature": "°C", "wind_speed": "m/s"}) == ["wind_speed_unit_expected_km/h"]
    assert validate_measurement_ranges({"humidity": 120, "ndvi": 1.2, "latitude": 11.667}) == ["humidity_above_range", "ndvi_above_range"]


def test_timestamp_handling_normalizes_to_utc():
    assert ensure_aware_utc("2026-08-29T11:30:00+05:30") == datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc)
    assert ensure_aware_utc(datetime(2026, 8, 29, 6, 0)) == datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc)


def test_simulation_live_mode_configuration_validation():
    simulation = Settings(DATA_MODE=DataMode.SIMULATION.value)
    assert simulation.data_mode == "simulation"

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DATA_MODE="simulation",
            JWT_SECRET_KEY="x" * 48,
            DATABASE_URL="postgresql+psycopg://user:strong-password@db.example.com:5432/firesight",
            CORS_ORIGINS="https://firesight.example",
        )


def test_environmental_snapshot_constructs_partial_missing_data_contract(monkeypatch):
    db = _session()

    class SessionFactory:
        def __call__(self):
            return db

    monkeypatch.setattr("backend.services.environmental_data_service.SessionLocal", SessionFactory())
    service = EnvironmentalDataService(weather_provider=FakeWeatherProvider(weather_payload()))
    snapshot = service.get_environmental_snapshot("r1")

    assert snapshot.region_id == "r1"
    assert isinstance(snapshot.weather, CanonicalWeatherData)
    assert snapshot.weather.temperature == 26.5
    assert snapshot.weather.observed_at.endswith("+05:30")
    assert isinstance(snapshot.vegetation, MissingEnvironmentalData)
    assert snapshot.vegetation.status == "UNAVAILABLE"
    assert snapshot.hotspots.status == "UNAVAILABLE"
    assert snapshot.availability == {
        "weather_available": True,
        "vegetation_available": False,
        "hotspots_available": False,
    }
    assert snapshot.provenance["weather"]["provider"] == "open-meteo"


def test_simulation_mode_does_not_call_live_weather_for_latest_weather():
    provider = FakeWeatherProvider(weather_payload())
    service = EnvironmentalDataService(weather_provider=provider, settings=Settings(DATA_MODE="simulation"))

    weather = service.get_latest_weather("r1")

    assert weather.status == "SIMULATED"
    assert provider.calls == []


def test_simulation_mode_snapshot_does_not_call_live_provider():
    provider = FakeWeatherProvider(weather_payload())
    service = EnvironmentalDataService(weather_provider=provider, settings=Settings(DATA_MODE="simulation"))

    snapshot = service.get_environmental_snapshot("r1")

    assert snapshot.data_mode == "simulation"
    assert snapshot.weather.status == "SIMULATED"
    assert snapshot.availability["weather_available"] is False
    assert snapshot.provenance["weather"]["quality_status"] == "SIMULATED"
    assert provider.calls == []


def test_provider_error_classification():
    assert classify_provider_error(status_code=401) == ProviderErrorKind.AUTHENTICATION_ERROR
    assert classify_provider_error(status_code=429) == ProviderErrorKind.RATE_LIMITED
    assert classify_provider_error(status_code=503) == ProviderErrorKind.PROVIDER_UNAVAILABLE
    assert classify_provider_error(TimeoutExample()) == ProviderErrorKind.TIMEOUT


def test_freshness_policy_uses_centralized_settings():
    settings = Settings(WEATHER_RECENT_MINUTES=15, WEATHER_STALE_MINUTES=90, VEGETATION_MAX_AGE_DAYS=7, HOTSPOT_MAX_AGE_HOURS=12)
    policy = FreshnessPolicy.from_settings(settings)

    assert policy.weather_recent == timedelta(minutes=15)
    assert policy.weather_max_age == timedelta(minutes=90)
    assert policy.vegetation_max_age == timedelta(days=7)
    assert policy.hotspot_max_age == timedelta(hours=12)
