import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.core.config import DEVELOPMENT_DEMO_PASSWORD, DEVELOPMENT_JWT_SECRET, Settings, get_settings
from backend.routes import weather

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cors_origins_parse_from_comma_separated_env_value():
    settings = Settings(CORS_ORIGINS="https://firesight.example,https://admin.firesight.example")

    assert settings.cors_origins == ["https://firesight.example", "https://admin.firesight.example"]


def test_cors_origins_parse_from_real_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://firesight.example,https://admin.firesight.example")

    settings = Settings()

    assert settings.cors_origins == ["https://firesight.example", "https://admin.firesight.example"]


def test_production_rejects_development_secret():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=DEVELOPMENT_JWT_SECRET,
            DATABASE_URL="postgresql+psycopg://user:strong-password@db.example.com:5432/firesight",
            CORS_ORIGINS="https://firesight.example",
        )


def test_database_url_accepts_common_platform_postgres_scheme():
    settings = Settings(DATABASE_URL="postgres://user:strong-password@db.example.com:5432/firesight")

    assert settings.database_url == "postgresql+psycopg://user:strong-password@db.example.com:5432/firesight"


def test_production_rejects_local_database_url():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="x" * 48,
            DATABASE_URL="postgresql+psycopg://firesight:firesight@localhost:5432/firesight",
            CORS_ORIGINS="https://firesight.example",
        )


def test_production_rejects_default_demo_login_password():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="x" * 48,
            DATABASE_URL="postgresql+psycopg://user:strong-password@db.example.com:5432/firesight",
            CORS_ORIGINS="https://firesight.example",
            DEMO_LOGIN_PASSWORD=DEVELOPMENT_DEMO_PASSWORD,
        )


def test_production_rejects_wildcard_and_loopback_cors():
    for origin in ["*", "http://localhost:5173", "http://127.0.0.1:5173"]:
        with pytest.raises(ValidationError):
            Settings(
                ENVIRONMENT="production",
                JWT_SECRET_KEY="x" * 48,
                DATABASE_URL="postgresql+psycopg://user:strong-password@db.example.com:5432/firesight",
                CORS_ORIGINS=origin,
            )


def test_public_config_redacts_secrets_and_exposes_paths():
    settings = Settings(
        JWT_SECRET_KEY="super-secret-value-that-should-never-render",
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/firesight",
        REDIS_URL="redis://localhost:6379/0",
        WEATHER_API_KEY="weather-secret",
        CLOUDINARY_URL="cloudinary://secret",
    )

    public_config = settings.public_config()
    serialized = str(public_config)

    assert public_config["database_configured"] is True
    assert public_config["weather_api_configured"] is True
    assert public_config["cloudinary_configured"] is True
    assert public_config["data_mode"] == "live"
    assert public_config["demo_login_enabled"] is True
    assert public_config["artifact_directories"]["models"] == "backend/artifacts/models"
    assert public_config["performance"]["vegetation_max_age_days"] == 5
    assert public_config["performance"]["hotspot_max_age_hours"] == 24
    assert "super-secret" not in serialized
    assert "weather-secret" not in serialized
    assert "cloudinary://secret" not in serialized


def test_weather_debug_endpoint_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:strong-password@db.example.com:5432/firesight")
    monkeypatch.setenv("CORS_ORIGINS", "https://firesight.example")
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", "production-demo-password")
    get_settings.cache_clear()

    try:
        with pytest.raises(HTTPException) as exc_info:
            weather.weather_debug(region_id="r1")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Debug endpoint is disabled in production"
    finally:
        get_settings.cache_clear()


def test_vercel_configuration_sets_frontend_security_headers():
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text())
    headers = {entry["key"]: entry["value"] for entry in config["headers"][0]["headers"]}

    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_docker_compose_declares_postgis_health_and_demo_login_env():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text()

    assert "image: postgis/postgis:" in compose
    assert "condition: service_healthy" in compose
    assert compose.count("      DEMO_LOGIN_ENABLED:") == 3
    assert compose.count("      DEMO_LOGIN_EMAIL:") == 3
    assert compose.count("      DEMO_LOGIN_PASSWORD:") == 3
