from fastapi import APIRouter, HTTPException, Query

from backend.core.config import PRODUCTION_ENVIRONMENTS, get_settings
from backend.schemas.domain import FireWeatherIndexRequest
from backend.services.weather_provider import OpenMeteoWeatherProvider
from backend.services.weather_engine import WeatherEngine

router = APIRouter()
engine = WeatherEngine()
provider = OpenMeteoWeatherProvider()


@router.get("/")
def get_weather(
    region_id: str = Query(default="r1"),
    forecast_days: int = Query(default=3, ge=1, le=7),
):
    try:
        return provider.weather_for_region(region_id=region_id, forecast_days=forecast_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/fire-weather-index")
def calculate_fire_weather_index(payload: FireWeatherIndexRequest):
    record = payload.model_dump()
    fire_weather_risk_index = engine.calculate_fire_weather_index(
        temperature=payload.temperature,
        humidity=payload.humidity,
        wind_speed=payload.wind_speed,
        rainfall=payload.rainfall,
    )
    return {
        "fire_weather_risk_index": fire_weather_risk_index,
        "fire_weather_index": fire_weather_risk_index,
        "metric_label": "Fire Weather Risk Index",
        "note": "This is an application-specific fire-weather risk indicator, not the official Canadian Forest Fire Weather Index.",
        "summary": engine.summarize(record),
        "alert_flags": engine.alert_flags(record),
    }


@router.get("/forecast")
def get_forecast(
    region_id: str = Query(default="r1"),
    forecast_days: int = Query(default=3, ge=1, le=7),
):
    try:
        weather = provider.weather_for_region(region_id=region_id, forecast_days=forecast_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "status": weather["status"],
        "provider": weather["provider"],
        "location": weather["location"],
        "hourly": weather.get("hourly", []),
        "daily": weather.get("daily", []),
        "retrieved_at": weather.get("retrieved_at"),
        "cache": weather.get("cache"),
        "source": weather.get("source"),
    }


@router.get("/debug")
def weather_debug(region_id: str = Query(default="r1")):
    if get_settings().environment in PRODUCTION_ENVIRONMENTS:
        raise HTTPException(status_code=404, detail="Debug endpoint is disabled in production")
    try:
        return provider.debug_for_region(region_id=region_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/compare")
def compare_weather_reference(
    region_id: str = Query(default="r1"),
    reference_temperature: float | None = None,
    reference_humidity: float | None = None,
    reference_wind_speed: float | None = None,
    reference_rainfall: float | None = None,
    reference_source: str = Query(default="Google Weather reference"),
):
    try:
        return provider.comparison(
            region_id=region_id,
            reference_temperature=reference_temperature,
            reference_humidity=reference_humidity,
            reference_wind_speed=reference_wind_speed,
            reference_rainfall=reference_rainfall,
            reference_source=reference_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/history/analyze")
def analyze_weather_history(records: list[dict]):
    return engine.historical_trend(records)
