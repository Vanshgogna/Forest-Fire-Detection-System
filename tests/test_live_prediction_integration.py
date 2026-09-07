from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import app
from backend.ml.features import FEATURE_COLUMNS, FEATURE_DEFAULTS
from backend.ml.pipeline import FireRiskModelService
from backend.schemas.environmental import CanonicalHotspotData, CanonicalVegetationData, CanonicalWeatherData, EnvironmentalSnapshot, MissingEnvironmentalData
from backend.services.environmental_foundation import CANONICAL_UNITS, DataMode, DataQualityStatus, ProviderName, ProviderType
from backend.services.live_prediction_service import LivePredictionService

client = TestClient(app)


class FakeEnvironmentalService:
    def __init__(self, snapshot: EnvironmentalSnapshot):
        self.snapshot = snapshot
        self.calls: list[str] = []

    def get_environmental_snapshot(self, region_id: str) -> EnvironmentalSnapshot:
        self.calls.append(region_id)
        return self.snapshot


def _snapshot(
    *,
    weather: CanonicalWeatherData | MissingEnvironmentalData | None = None,
    vegetation: CanonicalVegetationData | MissingEnvironmentalData | None = None,
    hotspots: CanonicalHotspotData | MissingEnvironmentalData | None = None,
    data_mode: str = DataMode.LIVE.value,
) -> EnvironmentalSnapshot:
    observed_at = "2026-08-29T11:30:00+05:30"
    retrieved_at = "2026-08-29T06:05:00+00:00"
    weather = weather or CanonicalWeatherData(
        temperature=29.0,
        humidity=52.0,
        wind_speed=18.0,
        precipitation=0.4,
        fire_weather_index=61.0,
        observed_at=observed_at,
        retrieved_at=retrieved_at,
        units=CANONICAL_UNITS,
    )
    vegetation = vegetation or CanonicalVegetationData(
        status=DataQualityStatus.LIVE,
        provider=ProviderName.SENTINEL_2.value,
        source_type="sentinel_ndvi_processing",
        ndvi_mean=0.37,
        captured_at=observed_at,
        processed_at=retrieved_at,
        scene_id="S2A_TEST_SCENE",
        product_id="S2A_TEST_PRODUCT",
        valid_pixel_percentage=91.0,
        values={"ndvi": 0.37, "ndvi_mean": 0.37, "valid_pixel_percentage": 91.0},
    )
    hotspots = hotspots or CanonicalHotspotData(
        status=DataQualityStatus.LIVE,
        provider=ProviderName.NASA_FIRMS.value,
        source_type="firms_area_csv",
        hotspot_count_24h=3,
        hotspot_count_48h=4,
        hotspot_count_7d=7,
        latest_detection_at=observed_at,
        retrieved_at=retrieved_at,
        values={"hotspot_count_24h": 3},
    )
    return EnvironmentalSnapshot(
        region_id="r1",
        timestamp=datetime(2026, 8, 29, 6, 5, tzinfo=timezone.utc),
        data_mode=data_mode,
        region={"region_id": "r1", "region": "Bandipur Tiger Reserve", "state": "Karnataka"},
        weather=weather,
        vegetation=vegetation,
        hotspots=hotspots,
        provenance={
            "weather": {"provider": ProviderName.OPEN_METEO.value, "provider_type": ProviderType.WEATHER.value, "quality_status": "LIVE"},
            "vegetation": {"provider": ProviderName.SENTINEL_2.value, "provider_type": ProviderType.SATELLITE.value, "quality_status": "LIVE"},
            "hotspots": {"provider": ProviderName.NASA_FIRMS.value, "provider_type": ProviderType.HOTSPOT.value, "quality_status": "LIVE"},
        },
        quality={"overall_status": "LIVE", "weather_status": "LIVE", "vegetation_status": "LIVE", "hotspot_status": "LIVE"},
        availability={"weather_available": True, "vegetation_available": True, "hotspots_available": True},
    )


def _service(snapshot: EnvironmentalSnapshot, data_mode: str = DataMode.LIVE.value) -> LivePredictionService:
    return LivePredictionService(
        environmental_service=FakeEnvironmentalService(snapshot),
        model_service=FireRiskModelService(),
        settings=Settings(DATA_MODE=data_mode),
    )


def test_environmental_snapshot_maps_to_exact_existing_feature_schema():
    service = _service(_snapshot())

    features, missing, defaulted = service.features_from_snapshot(_snapshot())

    assert list(features) == FEATURE_COLUMNS
    assert missing == []
    assert features == {
        "temperature": 29.0,
        "humidity": 52.0,
        "wind_speed": 18.0,
        "rainfall": 0.4,
        "ndvi": 0.37,
        "nbr": FEATURE_DEFAULTS["nbr"],
        "hotspots": 3.0,
        "fire_weather_index": 61.0,
    }
    assert defaulted == ["nbr"]


def test_environmental_snapshot_uses_real_nbr_when_available():
    vegetation = CanonicalVegetationData(
        status=DataQualityStatus.LIVE,
        provider=ProviderName.SENTINEL_2.value,
        source_type="sentinel_ndvi_processing",
        ndvi_mean=0.37,
        nbr_mean=0.18,
        captured_at="2026-08-29T11:30:00+05:30",
        processed_at="2026-08-29T06:05:00+00:00",
        scene_id="S2A_TEST_SCENE",
        product_id="S2A_TEST_PRODUCT",
        valid_pixel_percentage=91.0,
        nbr_valid_pixel_percentage=91.0,
        values={"ndvi": 0.37, "ndvi_mean": 0.37, "nbr": 0.18, "nbr_mean": 0.18, "valid_pixel_percentage": 91.0},
    )
    service = _service(_snapshot(vegetation=vegetation))

    features, missing, defaulted = service.features_from_snapshot(_snapshot(vegetation=vegetation))

    assert missing == []
    assert features["nbr"] == 0.18
    assert defaulted == []


def test_valid_environmental_snapshot_produces_prediction_with_existing_risk_fields():
    result = _service(_snapshot()).predict_region("r1")

    assert result["status"] == "ok"
    assert result["risk_score"] >= 0
    assert result["risk_level"] in {"Low", "Moderate", "High", "Critical"}
    assert result["confidence"] >= 0
    assert result["input_snapshot"]["source"] == "environmental_snapshot"
    assert result["feature_schema"] == FEATURE_COLUMNS


def test_explainability_uses_actual_prediction_features():
    result = _service(_snapshot()).predict_region("r1")
    features = result["feature_values"]

    explained_values = {item["feature"]: item["value"] for item in result["top_contributing_features"]}

    assert result["explanation_details"]["prediction"] == result["risk_level"]
    assert result["visual_explanations"]["risk_breakdown"]["risk_score"] == result["risk_score"]
    assert explained_values
    assert all(explained_values[feature] == features[feature] for feature in explained_values)


def test_live_prediction_endpoint_uses_environmental_snapshot_not_fixture_risk(monkeypatch):
    live_snapshot = _snapshot(
        weather=CanonicalWeatherData(
            temperature=22.2,
            humidity=64.0,
            wind_speed=9.0,
            precipitation=1.1,
            fire_weather_index=34.0,
            observed_at="2026-08-29T11:30:00+05:30",
            retrieved_at="2026-08-29T06:05:00+00:00",
            units=CANONICAL_UNITS,
        )
    )
    monkeypatch.setattr("backend.routes.prediction.live_prediction_service", _service(live_snapshot))

    response = client.get("/api/prediction/r1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["input_snapshot"]["temperature"] == 22.2
    assert payload["input_snapshot"]["temperature"] != 29
    assert payload["input_snapshot"]["source"] == "environmental_snapshot"


def test_missing_live_environmental_data_returns_unavailable_without_prediction():
    missing_ndvi = MissingEnvironmentalData(status=DataQualityStatus.UNAVAILABLE, reason="Sentinel NDVI is not ready.")

    result = _service(_snapshot(vegetation=missing_ndvi)).predict_region("r1")

    assert result["status"] == "unavailable"
    assert "risk_score" not in result
    assert result["missing_sources"] == [{"source": "vegetation", "status": "UNAVAILABLE", "reason": "Sentinel NDVI is not ready."}]


def test_existing_simulation_mode_prediction_still_uses_fixture_behavior():
    service = LivePredictionService(model_service=FireRiskModelService(), settings=Settings(DATA_MODE=DataMode.SIMULATION.value))

    result = service.predict_region("r1")

    assert result["status"] == "ok"
    assert result["data_mode"] == "simulation"
    assert result["region"] == "Bandipur Tiger Reserve"
    assert result["input_snapshot"]["source"] == "environmental_snapshot"
