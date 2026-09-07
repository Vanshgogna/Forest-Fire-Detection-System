from fastapi.testclient import TestClient

from backend.core.security import create_access_token
from backend.main import app
from backend.schemas.environmental import MissingEnvironmentalData
from backend.services.environmental_foundation import DataQualityStatus
from backend.services.environmental_data_service import EnvironmentalDataService

client = TestClient(app)


def auth_headers(role: str = "admin"):
    token = create_access_token("qa@firesight.ai", {"role": role, "scopes": ["qa"]})
    return {"Authorization": f"Bearer {token}"}


def test_public_read_endpoints_are_available():
    endpoints = [
        "/api/health",
        "/api/readiness",
        "/api/dashboard/overview",
        "/api/dashboard/top-risk-regions",
        "/api/weather/",
        "/api/weather/forecast",
        "/api/weather/debug",
        "/api/weather/compare?reference_temperature=29",
        "/api/environmental-snapshot/r1",
        "/api/vegetation/summary",
        "/api/vegetation/satellite/tiles/S2A_TILE_001",
        "/api/hotspots/",
        "/api/prediction/",
        "/api/prediction/explainability",
        "/api/gis/regions",
        "/api/gis/layers",
        "/api/gis/risk-geojson",
        "/api/gis/heatmap",
        "/api/gis/search?query=forest&min_risk=20",
        "/api/gis/spatial-statistics",
        "/api/gis/cache-manifest/risk",
        "/api/monitoring/health",
        "/api/monitoring/health/backend",
        "/api/monitoring/health/database",
        "/api/monitoring/health/cache",
        "/api/monitoring/health/weather-api",
        "/api/monitoring/health/satellite-pipeline",
        "/api/monitoring/health/prediction-engine",
        "/api/monitoring/health/gis-engine",
        "/api/alerts/",
        "/api/analytics/summary",
        "/api/reports/",
        "/api/settings/",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, endpoint


def test_auth_login_success_and_failure_contracts():
    success = client.post("/api/auth/login", json={"email": "officer@firesight.ai", "password": "development-demo-password-change-me"})
    failure = client.post("/api/auth/login", json={"email": "officer@firesight.ai", "password": "wrong-password"})

    assert success.status_code == 200
    assert success.json()["access_token"]
    assert success.json()["refresh_token"]
    assert failure.status_code == 401


def test_prediction_post_and_batch_contracts():
    payload = {"region": "Bandipur Tiger Reserve", "temperature": 39, "humidity": 18, "wind_speed": 24, "ndvi": 0.31, "hotspots": 18}

    single = client.post("/api/prediction/", json=payload)
    batch = client.post("/api/prediction/batch", json=[payload, payload])

    assert single.status_code == 200
    assert single.json()["risk_level"] in {"Low", "Moderate", "High", "Critical"}
    assert single.json()["input_snapshot"]["temperature"] == payload["temperature"]
    assert single.json()["input_snapshot"]["humidity"] == payload["humidity"]
    assert single.json()["input_snapshot"]["wind_speed"] == payload["wind_speed"]
    assert single.json()["explanation"]
    assert single.json()["explanation_details"]["why"]
    assert single.json()["top_contributing_features"]
    assert single.json()["weather_influence"]
    assert single.json()["vegetation_influence"]
    assert single.json()["historical_comparison"]
    assert single.json()["visual_explanations"]["contribution_bars"]
    assert single.json()["recommendation_rationales"]
    assert batch.status_code == 200
    assert len(batch.json()["predictions"]) == 2
    assert batch.json()["predictions"][0]["explanation_details"]["why"]


def test_environmental_snapshot_contract_represents_missing_data(monkeypatch):
    def missing_vegetation(self, region_id: str):
        return MissingEnvironmentalData(status=DataQualityStatus.UNAVAILABLE, reason=f"Vegetation unavailable in contract test for {region_id}.")

    def missing_hotspots(self, region_id: str):
        return MissingEnvironmentalData(status=DataQualityStatus.UNAVAILABLE, reason=f"Hotspots unavailable in contract test for {region_id}.")

    monkeypatch.setattr(EnvironmentalDataService, "get_latest_vegetation", missing_vegetation)
    monkeypatch.setattr(EnvironmentalDataService, "get_recent_hotspots", missing_hotspots)

    response = client.get("/api/environmental-snapshot/r1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["region_id"] == "r1"
    assert payload["availability"]["weather_available"] in {True, False}
    assert payload["availability"]["vegetation_available"] is False
    assert payload["availability"]["hotspots_available"] is False
    assert payload["vegetation"]["status"] == "UNAVAILABLE"
    assert payload["vegetation"]["values"] is None
    assert payload["hotspots"]["status"] == "UNAVAILABLE"
    assert payload["hotspots"]["values"] is None
    assert payload["provenance"]["vegetation"]["provider_type"] == "SATELLITE"
    assert payload["provenance"]["hotspots"]["provider_type"] == "HOTSPOT"


def test_gis_and_remote_sensing_validation_contracts():
    indices = client.post("/api/vegetation/indices", json={"nir": 0.72, "red": 0.21, "swir": 0.38, "cloud_percentage": 12})
    invalid_indices = client.post("/api/vegetation/indices", json={"nir": 2, "red": 0.21, "swir": 0.38})
    scene_plan = client.post(
        "/api/vegetation/satellite/scene-plan",
        json={"scene_id": "S2A_TILE_001", "source": "Sentinel-2", "acquisition_date": "2026-08-09", "cloud_percentage": 12},
    )
    invalid_scene = client.post("/api/vegetation/satellite/scene-plan", json={"source": "Unknown"})

    assert indices.status_code == 200
    assert "vegetation_health_index" in indices.json()
    assert invalid_indices.status_code == 422
    assert scene_plan.status_code == 200
    assert scene_plan.json()["validation"]["valid"] is True
    assert invalid_scene.status_code == 422


def test_protected_endpoints_enforce_roles():
    viewer_headers = auth_headers("viewer")
    officer_headers = auth_headers("forest_officer")
    admin_headers = auth_headers("admin")
    researcher_headers = auth_headers("researcher")

    assert client.get("/api/users/", headers=viewer_headers).status_code == 403
    assert client.get("/api/users/", headers=admin_headers).status_code == 200
    assert client.get("/api/users/me", headers=viewer_headers).status_code == 200
    assert client.get("/api/admin/system-health", headers=viewer_headers).status_code == 403
    assert client.get("/api/admin/system-health", headers=admin_headers).status_code == 200
    assert client.post("/api/notifications/", json={"channel": "dashboard", "body": "QA"}, headers=viewer_headers).status_code == 403
    assert client.post("/api/notifications/", json={"channel": "dashboard", "body": "QA"}, headers=officer_headers).status_code == 200
    assert client.post("/api/prediction/train", json={"algorithm": "random_forest"}, headers=viewer_headers).status_code == 403
    assert client.post("/api/prediction/train", json={"algorithm": "random_forest"}, headers=researcher_headers).status_code == 200


def test_monitoring_endpoints_are_protected_and_report_platform_health():
    viewer_headers = auth_headers("viewer")
    admin_headers = auth_headers("admin")

    assert client.get("/api/monitoring/metrics", headers=viewer_headers).status_code == 403
    metrics = client.get("/api/monitoring/metrics", headers=admin_headers)
    dashboard = client.get("/api/monitoring/dashboard", headers=admin_headers)
    model = client.get("/api/monitoring/model", headers=admin_headers)
    alerts = client.get("/api/monitoring/alerts", headers=admin_headers)

    assert metrics.status_code == 200
    assert "api_response_time_ms" in metrics.json()
    assert "request_count" in metrics.json()
    assert dashboard.status_code == 200
    assert "system_health" in dashboard.json()
    assert "api_performance" in dashboard.json()
    assert "model_performance" in dashboard.json()
    assert "dataset_status" in dashboard.json()
    assert "storage_usage" in dashboard.json()
    assert "recent_errors" in dashboard.json()
    assert model.status_code == 200
    assert "confidence_distribution" in model.json()
    assert alerts.status_code == 200
    assert "alerts" in alerts.json()
