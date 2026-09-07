from fastapi.testclient import TestClient

from backend.core.security import create_access_token
from backend.main import app

client = TestClient(app)


def auth_headers(role: str = "admin"):
    token = create_access_token("tester@firesight.ai", {"role": role, "scopes": ["tests"]})
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_overview_contract():
    response = client.get("/api/dashboard/overview")
    assert response.status_code == 200
    payload = response.json()
    assert "risk" in payload
    assert "weather" in payload
    assert "hotspots" in payload
    assert "alerts" in payload


def test_weather_fire_weather_index_flags():
    response = client.post(
        "/api/weather/fire-weather-index",
        json={"temperature": 42, "humidity": 16, "wind_speed": 38, "rainfall": 0, "uv_index": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["fire_weather_index"] > 0
    assert "high_temperature" in payload["alert_flags"]
    assert "strong_wind" in payload["alert_flags"]


def test_weather_fire_weather_index_validation_failure():
    response = client.post(
        "/api/weather/fire-weather-index",
        json={"temperature": 42, "humidity": 120, "wind_speed": 38, "rainfall": 0},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_admin_requires_admin_role():
    forbidden = client.get("/api/admin/system-health", headers=auth_headers("viewer"))
    assert forbidden.status_code == 403
    allowed = client.get("/api/admin/system-health", headers=auth_headers("admin"))
    assert allowed.status_code == 200
    assert "cache" in allowed.json()
    assert "components" in allowed.json()
    assert "metrics" in allowed.json()
    assert "alerts" in allowed.json()


def test_notification_queue_requires_operator_role():
    response = client.post(
        "/api/notifications/",
        json={"channel": "dashboard", "recipient": "control-room", "subject": "Test", "body": "Body"},
        headers=auth_headers("forest_officer"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_versioned_prediction_alias():
    response = client.get("/api/v1/prediction/explainability")
    assert response.status_code == 200
    payload = response.json()
    if payload.get("status") == "unavailable":
        assert payload["message"] == "Live weather is required before generating a current explainability sample."
    else:
        assert "feature_importance" in payload
