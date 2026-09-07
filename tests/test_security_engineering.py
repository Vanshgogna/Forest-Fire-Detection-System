from fastapi.testclient import TestClient

from backend.core.security import Principal
from backend.main import app


def test_security_headers_include_csp_and_clickjacking_protection():
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_unexpected_request_fields_are_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/weather/fire-weather-index",
        json={
            "temperature": 35,
            "humidity": 28,
            "wind_speed": 12,
            "rainfall": 0,
            "unexpected": "reject-me",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_request_size_limit_rejects_large_bodies():
    client = TestClient(app)
    response = client.post(
        "/api/weather/fire-weather-index",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "999999999"},
    )

    assert response.status_code == 413
    assert response.json()["message"] == "Request body is too large"


def test_malformed_content_length_is_rejected_safely():
    client = TestClient(app)
    response = client.post(
        "/api/weather/fire-weather-index",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "invalid"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Invalid Content-Length header"


def test_idempotency_key_replay_is_rejected_for_mutating_requests():
    client = TestClient(app)
    payload = {"temperature": 35, "humidity": 28, "wind_speed": 12, "rainfall": 0}
    headers = {"X-Idempotency-Key": "security-test-replay"}

    first = client.post("/api/weather/fire-weather-index", json=payload, headers=headers)
    second = client.post("/api/weather/fire-weather-index", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["message"] == "Duplicate request rejected"


def test_principal_scopes_are_not_shared_between_instances():
    first = Principal(subject="one")
    second = Principal(subject="two")

    first.scopes.append("admin:test")

    assert second.scopes == []
