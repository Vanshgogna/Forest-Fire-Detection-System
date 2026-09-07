from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_prediction_explainability_contract():
    response = client.get("/api/prediction/explainability")
    assert response.status_code == 200
    payload = response.json()
    if payload.get("status") == "unavailable":
        assert payload["message"] == "Live weather is required before generating a current explainability sample."
        assert payload["weather"]["status"] == "unavailable"
        return
    assert "feature_importance" in payload
    assert "recommendations" in payload
    assert "explanation_details" in payload
    assert payload["explanation_details"]["top_contributing_features"]
    assert payload["explanation_details"]["visual_explanations"]["confidence_gauge"]
    assert payload["explanation_details"]["weather_source"]["provider"] == "open-meteo"
