from fastapi.testclient import TestClient
import logging

from backend.core.errors import DatasetError
from backend.core.logging import safe_request_id
from backend.main import app


@app.get("/api/qa/error-handling/app-error", include_in_schema=False)
def raise_app_error():
    raise DatasetError("The uploaded dataset is missing required fire-risk columns.")


@app.get("/api/qa/error-handling/unexpected", include_in_schema=False)
def raise_unexpected_error():
    raise RuntimeError("database password leaked in stack trace")


def test_validation_error_is_sanitized():
    client = TestClient(app)
    response = client.post("/api/weather/fire-weather-index", json={"temperature": 35, "humidity": 180, "wind_speed": 18, "rainfall": 0})
    payload = response.json()

    assert response.status_code == 422
    assert payload["error"] == "validation_error"
    assert payload["message"] == "The request contains invalid or incomplete data."
    assert "input" not in str(payload["details"])
    assert response.headers["X-Request-ID"] == payload["error_id"]


def test_http_exception_uses_safe_shape():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": "officer@firesight.ai", "password": "wrong-password"})
    payload = response.json()

    assert response.status_code == 401
    assert payload["error"] == "http_error"
    assert payload["message"] == "Invalid email or password"
    assert payload["path"] == "/api/auth/login"


def test_application_error_uses_domain_code_without_internal_details():
    client = TestClient(app)
    response = client.get("/api/qa/error-handling/app-error", headers={"X-Request-ID": "qa-request-123"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["error"] == "dataset_error"
    assert payload["error_id"] == "qa-request-123"
    assert "password" not in str(payload).lower()


def test_unexpected_error_is_shielded_from_clients(caplog):
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        response = client.get("/api/qa/error-handling/unexpected")
    payload = response.json()

    assert response.status_code == 500
    assert payload["error"] == "internal_server_error"
    assert payload["message"] == "The service could not complete the request."
    assert "password" not in str(payload).lower()
    assert "stack" not in str(payload).lower()
    assert "password" not in caplog.text.lower()


def test_request_id_is_bounded_and_sanitized():
    assert safe_request_id("abc-123_XYZ") == "abc-123_XYZ"
    assert safe_request_id("token with spaces and !@#$") == "tokenwithspacesand"
    assert len(safe_request_id("a" * 200)) == 80
