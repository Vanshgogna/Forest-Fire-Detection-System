from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from backend.services.cache import CacheService
from backend.services.weather_provider import OpenMeteoWeatherProvider


def current_provider_time() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def open_meteo_payload(temperature: float = 29.4, observed_at: str = "2026-08-29T10:45") -> dict:
    return {
        "latitude": 11.667,
        "longitude": 76.629,
        "timezone": "Asia/Kolkata",
        "current_units": {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
            "rain": "mm",
            "surface_pressure": "hPa",
            "cloud_cover": "%",
        },
        "current": {
            "time": observed_at,
            "temperature_2m": temperature,
            "apparent_temperature": 31.0,
            "relative_humidity_2m": 72,
            "wind_speed_10m": 9.5,
            "wind_direction_10m": 240,
            "wind_gusts_10m": 18.2,
            "precipitation": 0.1,
            "rain": 0.1,
            "surface_pressure": 1008.4,
            "cloud_cover": 84,
        },
        "hourly": {
            "time": ["2026-08-29T10:00", "2026-08-29T11:00"],
            "temperature_2m": [29.4, 29.9],
            "apparent_temperature": [31.0, 31.4],
            "relative_humidity_2m": [72, 70],
            "wind_speed_10m": [9.5, 10.0],
            "wind_direction_10m": [240, 250],
            "wind_gusts_10m": [18.2, 18.8],
            "precipitation": [0.1, 0],
            "rain": [0.1, 0],
            "surface_pressure": [1008.4, 1008.1],
            "cloud_cover": [84, 80],
            "uv_index": [2.1, 1.8],
        },
        "daily": {
            "time": ["2026-08-29"],
            "temperature_2m_max": [30.4],
            "temperature_2m_min": [22.1],
            "apparent_temperature_max": [32.2],
            "precipitation_sum": [2.4],
            "rain_sum": [2.4],
            "wind_speed_10m_max": [13.4],
            "wind_gusts_10m_max": [22.3],
            "wind_direction_10m_dominant": [245],
            "uv_index_max": [5.2],
        },
    }


def provider_with_transport(handler):
    cache = CacheService()
    cache.client = None
    CacheService._memory_cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenMeteoWeatherProvider(cache=cache, client=client)


def expire_primary_weather_cache(provider: OpenMeteoWeatherProvider, region_id: str = "r1", forecast_days: int = 3) -> None:
    params = provider._params(provider.region_reference(region_id), forecast_days=forecast_days)
    key = provider._cache_key(params)
    expires_at, value = CacheService._memory_cache[key]
    assert expires_at > time.time()
    CacheService._memory_cache[key] = (time.time() - 1, value)


def test_open_meteo_weather_is_requested_with_region_coordinates_and_units():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=open_meteo_payload())

    provider = provider_with_transport(handler)
    payload = provider.weather_for_region("r1")

    assert payload["status"] == "ok"
    assert payload["provider"] == "open-meteo"
    assert payload["location"]["region"] == "Bandipur Tiger Reserve"
    assert payload["location"]["latitude"] == 11.667
    assert payload["location"]["longitude"] == 76.629
    assert payload["location"]["timezone"] == "Asia/Kolkata"
    assert payload["units"]["temperature"] == "°C"
    assert payload["units"]["wind_speed"] == "km/h"
    assert payload["units"]["rainfall"] == "mm"
    assert payload["current"]["temperature"] == 29.4
    assert payload["current"]["observed_at"] == "2026-08-29T10:45"
    assert payload["current"]["metric_label"] == "Fire Weather Risk Index"
    assert payload["displayed_variable"]["provider_variable"] == "temperature_2m"
    assert payload["displayed_variable"]["description"].startswith("Air temperature at 2 meters")
    assert payload["request"]["params"]["latitude"] == 11.667
    assert payload["request"]["params"]["longitude"] == 76.629
    assert payload["request"]["params"]["timezone"] == "Asia/Kolkata"
    assert payload["timestamp_analysis"]["timezone"] == "Asia/Kolkata"
    assert payload["timestamp_analysis"]["provider_local_time"].startswith("2026-08-29T10:45")
    assert "current" in requests[0].url.params
    assert requests[0].url.params["temperature_unit"] == "celsius"
    assert requests[0].url.params["wind_speed_unit"] == "kmh"
    assert requests[0].url.params["precipitation_unit"] == "mm"


def test_open_meteo_successful_live_weather_response_is_marked_live():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=open_meteo_payload(temperature=29.1, observed_at=current_provider_time()))

    provider = provider_with_transport(handler)
    payload = provider.weather_for_region("r1")

    assert payload["status"] == "ok"
    assert payload["data_status"] == "LIVE"
    assert payload["cache"]["status"] == "miss"
    assert payload["current"]["temperature"] == 29.1


def test_weather_provider_uses_cache_for_repeated_coordinate_requests():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=open_meteo_payload(temperature=28.7))

    provider = provider_with_transport(handler)
    first = provider.weather_for_region("r1")
    second = provider.weather_for_region("r1")

    assert calls == 1
    assert first["current"]["temperature"] == second["current"]["temperature"]
    assert second["cache"]["status"] == "hit"
    assert second["data_status"] in {"CACHED", "STALE"}


def test_weather_provider_failure_uses_recent_cache_without_new_mock_values():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls > 1:
            return httpx.Response(502, json={"error": "provider unavailable"})
        return httpx.Response(200, json=open_meteo_payload(temperature=27.2))

    provider = provider_with_transport(handler)
    first = provider.weather_for_region("r1")
    second = provider.weather_for_region("r1")

    assert calls == 1
    assert first["current"]["temperature"] == 27.2
    assert second["current"]["temperature"] == 27.2
    assert second["cache"]["status"] == "hit"


def test_weather_provider_failure_after_unusable_cache_expiration_is_unavailable():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls > 1:
            return httpx.Response(502, json={"error": "provider unavailable"})
        return httpx.Response(200, json=open_meteo_payload(temperature=26.5))

    provider = provider_with_transport(handler)
    first = provider.weather_for_region("r1")
    params = provider._params(provider.region_reference("r1"), forecast_days=3)
    key = provider._cache_key(params)
    CacheService._memory_cache[key] = (time.time() - 1, json.dumps(first, default=str))
    CacheService._memory_cache.pop(provider._fallback_cache_key(key), None)
    second = provider.weather_for_region("r1")

    assert calls == 3
    assert second["status"] == "unavailable"
    assert second["data_status"] == "UNAVAILABLE"
    assert "current" not in second


def test_weather_provider_failure_does_not_return_mock_weather():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "provider unavailable"})

    provider = provider_with_transport(handler)
    payload = provider.weather_for_region("r1")

    assert payload["status"] == "unavailable"
    assert payload["provider"] == "open-meteo"
    assert payload["message"] == "Live weather data is temporarily unavailable"
    assert "current" not in payload
    assert payload["location"]["region"] == "Bandipur Tiger Reserve"
    assert payload["data_status"] == "UNAVAILABLE"


def test_weather_provider_429_uses_cached_fallback_without_labeling_live():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=open_meteo_payload(temperature=26.8, observed_at=current_provider_time()))
        return httpx.Response(429, json={"reason": "rate limited"})

    provider = provider_with_transport(handler)
    first = provider.weather_for_region("r1")
    expire_primary_weather_cache(provider)
    second = provider.weather_for_region("r1")

    assert calls == 2
    assert first["data_status"] == "LIVE"
    assert second["status"] == "ok"
    assert second["data_status"] == "CACHED"
    assert second["current"]["temperature"] == 26.8
    assert second["cache"]["status"] == "hit"
    assert second["cache"]["fallback"] is True
    assert second["cache"]["fallback_reason"] == "RATE_LIMITED"
    assert second["provenance"]["quality_status"] == "CACHED"


def test_weather_provider_429_uses_stale_cached_fallback_when_available():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=open_meteo_payload(temperature=25.9))
        return httpx.Response(429, json={"reason": "rate limited"})

    provider = provider_with_transport(handler)
    provider.weather_for_region("r1")
    expire_primary_weather_cache(provider)
    payload = provider.weather_for_region("r1")

    assert calls == 2
    assert payload["status"] == "ok"
    assert payload["data_status"] == "STALE"
    assert payload["current"]["temperature"] == 25.9
    assert payload["cache"]["fallback"] is True
    assert payload["cache"]["fallback_reason"] == "RATE_LIMITED"
    assert payload["provenance"]["quality_status"] == "STALE"


def test_weather_provider_429_without_cached_data_is_unavailable_and_not_retried():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"reason": "rate limited"})

    provider = provider_with_transport(handler)
    payload = provider.weather_for_region("r1")
    repeated = provider.weather_for_region("r1")

    assert calls == 1
    assert payload["status"] == "unavailable"
    assert payload["data_status"] == "UNAVAILABLE"
    assert payload["error"] == "RATE_LIMITED"
    assert "current" not in payload
    assert repeated["status"] == "unavailable"
    assert repeated["cache"]["status"] == "hit"


def test_weather_provider_coalesces_simultaneous_same_region_requests():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return httpx.Response(200, json=open_meteo_payload(temperature=28.4, observed_at=current_provider_time()))

    provider = provider_with_transport(handler)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: provider.weather_for_region("r1"), range(2)))

    assert calls == 1
    assert results[0]["current"]["temperature"] == 28.4
    assert results[1]["current"]["temperature"] == 28.4
    assert {result["cache"]["status"] for result in results} == {"miss", "hit"}


def test_weather_provider_timeout_uses_cached_fallback():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=open_meteo_payload(temperature=24.6, observed_at=current_provider_time()))
        raise httpx.TimeoutException("open-meteo timeout", request=request)

    provider = provider_with_transport(handler)
    provider.weather_for_region("r1")
    expire_primary_weather_cache(provider)
    payload = provider.weather_for_region("r1")

    assert calls == 3
    assert payload["status"] == "ok"
    assert payload["data_status"] == "CACHED"
    assert payload["current"]["temperature"] == 24.6
    assert payload["cache"]["fallback_reason"] == "TIMEOUT"


def test_weather_provider_temporary_5xx_is_retried_once_then_live():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary provider failure"})
        return httpx.Response(200, json=open_meteo_payload(temperature=30.2, observed_at=current_provider_time()))

    provider = provider_with_transport(handler)
    payload = provider.weather_for_region("r1")

    assert calls == 2
    assert payload["status"] == "ok"
    assert payload["data_status"] == "LIVE"
    assert payload["current"]["temperature"] == 30.2
    assert payload["cache"]["status"] == "miss"


def test_weather_comparison_uses_configurable_quality_thresholds():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=open_meteo_payload(temperature=25.8))

    provider = provider_with_transport(handler)
    payload = provider.comparison("r1", reference_temperature=29, reference_humidity=58, reference_wind_speed=22.2, reference_rainfall=0.1)

    assert payload["metrics"]["temperature"]["difference"] == -3.2
    assert payload["metrics"]["temperature"]["quality"] == "warning"
    assert payload["metrics"]["humidity"]["quality"] == "informational"
    assert payload["thresholds"]["temperature_c"]["warning"] == 3.0
