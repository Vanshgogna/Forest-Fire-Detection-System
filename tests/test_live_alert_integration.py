from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class FakeLivePredictionService:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[str] = []

    def predict_region(self, region_id: str) -> dict:
        self.calls.append(region_id)
        return self.response


def _prediction(**overrides):
    response = {
        "status": "ok",
        "region_id": "r1",
        "region": "Bandipur Tiger Reserve",
        "data_mode": "live",
        "risk_score": 91,
        "risk_level": "Critical",
        "confidence": 94,
        "feature_values": {
            "temperature": 29.0,
            "humidity": 18.0,
            "wind_speed": 24.0,
            "rainfall": 0.0,
            "ndvi": 0.31,
            "nbr": 0.45,
            "hotspots": 18.0,
            "fire_weather_index": 78.0,
        },
        "input_snapshot": {"snapshot_timestamp": "2026-08-29T06:05:00+00:00"},
        "recommendations": ["Increase patrol readiness", "Review control room staffing"],
    }
    response.update(overrides)
    return response


def test_valid_live_prediction_is_evaluated_by_existing_alert_engine(monkeypatch):
    fake_service = FakeLivePredictionService(_prediction())
    monkeypatch.setattr("backend.routes.alerts.live_prediction_service", fake_service)

    response = client.get("/api/alerts/evaluate/r1")

    assert response.status_code == 200
    payload = response.json()
    assert fake_service.calls == ["r1"]
    assert payload["status"] == "ok"
    assert payload["source"] == "live_prediction"
    assert payload["alerts"]
    assert payload["alerts"][0]["severity"] == "Critical"
    assert payload["alerts"][0]["source"] == "live_prediction"
    assert payload["alerts"][0]["risk_score"] == 91


def test_unavailable_live_prediction_does_not_generate_alert(monkeypatch):
    fake_service = FakeLivePredictionService(
        {
            "status": "unavailable",
            "region_id": "r1",
            "region": "Bandipur Tiger Reserve",
            "message": "Live environmental data is unavailable for prediction.",
            "missing_sources": [{"source": "vegetation", "status": "UNAVAILABLE", "reason": "NDVI missing"}],
        }
    )
    monkeypatch.setattr("backend.routes.alerts.live_prediction_service", fake_service)

    response = client.get("/api/alerts/evaluate/r1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["alerts"] == []
    assert "risk_score" not in payload
    assert payload["missing_sources"][0]["source"] == "vegetation"


def test_fixture_alert_endpoint_labels_alerts_as_simulation():
    response = client.get("/api/alerts/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "simulation"
    assert payload["alerts"]
    assert all(alert["source"] == "simulation" for alert in payload["alerts"])
    assert all(alert["data_mode"] == "simulation" for alert in payload["alerts"])


def test_existing_explicit_alert_evaluation_still_passes():
    response = client.post(
        "/api/alerts/evaluate",
        json={
            "prediction": {"risk_score": 75},
            "weather": {"temperature": 29, "humidity": 40, "wind_speed": 12},
            "vegetation": {"ndvi": 0.5, "nbr": 0.45},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["alerts"] == [
        {"severity": "High", "title": "High wildfire probability", "reason": "Prediction score exceeds monitoring threshold."}
    ]
