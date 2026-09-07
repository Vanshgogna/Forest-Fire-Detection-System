from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

from backend.core.config import get_settings
from backend.services.cache import CacheService
from backend.services.environmental_foundation import (
    CANONICAL_UNITS,
    DataProvenance,
    DataQualityStatus,
    FreshnessPolicy,
    ProviderErrorKind,
    ProviderName,
    ProviderRequestMetadata,
    ProviderType,
    classify_freshness,
    classify_provider_error,
    provider_operation_completed,
    provider_operation_started,
    validate_canonical_units,
)
from backend.services.region_registry import get_region_location
from backend.services.weather_engine import WeatherEngine

CURRENT_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "rain",
    "surface_pressure",
    "cloud_cover",
]
HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "rain",
    "surface_pressure",
    "cloud_cover",
    "uv_index",
]
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "precipitation_sum",
    "rain_sum",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "uv_index_max",
]
logger = logging.getLogger("firesight.weather")
TRANSIENT_PROVIDER_ERRORS = {
    ProviderErrorKind.RATE_LIMITED,
    ProviderErrorKind.TIMEOUT,
    ProviderErrorKind.PROVIDER_UNAVAILABLE,
}
RETRIABLE_PROVIDER_ERRORS = {
    ProviderErrorKind.TIMEOUT,
    ProviderErrorKind.PROVIDER_UNAVAILABLE,
}
MAX_PROVIDER_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.15
RATE_LIMIT_COOLDOWN_SECONDS = 60
TRANSIENT_ERROR_COOLDOWN_SECONDS = 30
MAX_ERROR_CACHE_SECONDS = 600
COALESCED_WAIT_SECONDS = 10.0
COALESCED_POLL_SECONDS = 0.1


class WeatherProviderError(RuntimeError):
    pass


class OpenMeteoWeatherProvider:
    provider = ProviderName.OPEN_METEO.value
    provider_type = ProviderType.WEATHER
    source_type = "forecast_model_current_conditions"
    _local_locks: dict[str, Lock] = {}
    _local_locks_guard = Lock()

    def __init__(self, cache: CacheService | None = None, client: httpx.Client | None = None):
        self.settings = get_settings()
        self.cache = cache or CacheService()
        self.client = client or httpx.Client(timeout=self.settings.weather_request_timeout)
        self.engine = WeatherEngine()

    def region_reference(self, region_id: str | None) -> dict[str, Any]:
        return get_region_location(region_id).as_dict()

    def weather_for_region(self, region_id: str | None = None, forecast_days: int = 3) -> dict[str, Any]:
        location = self.region_reference(region_id)
        return self.weather_for_location(location=location, forecast_days=forecast_days)

    def fetch(self, request: ProviderRequestMetadata) -> dict[str, Any]:
        params = request.request or {}
        forecast_days = int(params.get("forecast_days", 3))
        return self.weather_for_region(region_id=request.region_id, forecast_days=forecast_days)

    def weather_for_location(self, location: dict[str, Any], forecast_days: int = 3) -> dict[str, Any]:
        params = self._params(location, forecast_days)
        cache_key = self._cache_key(params)
        metadata = ProviderRequestMetadata(
            provider=self.provider,
            provider_type=self.provider_type,
            operation="weather_for_location",
            region_id=location.get("region_id"),
            request=self._request_debug(params),
        )
        started = provider_operation_started(metadata)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        cached = self.cache.get_json(cache_key)
        if cached:
            payload = self._with_cache_metadata(cached, retrieved_at, cache_hit=True)
            provider_operation_completed(metadata, started, DataQualityStatus(payload["data_status"]), record_count=1)
            return payload

        lock = self._local_lock(cache_key)
        with lock:
            retrieved_at = datetime.now(timezone.utc).isoformat()
            cached = self.cache.get_json(cache_key)
            if cached:
                payload = self._with_cache_metadata(cached, retrieved_at, cache_hit=True)
                provider_operation_completed(metadata, started, DataQualityStatus(payload["data_status"]), record_count=1)
                return payload
            payload, error_kind = self._refresh_weather_cache(cache_key, location, params, retrieved_at)
            provider_operation_completed(
                metadata,
                started,
                DataQualityStatus(payload["data_status"]),
                record_count=1 if payload.get("status") == "ok" else 0,
                error_kind=error_kind,
            )
            return payload

    def _refresh_weather_cache(
        self,
        cache_key: str,
        location: dict[str, Any],
        params: dict[str, Any],
        retrieved_at: str,
    ) -> tuple[dict[str, Any], ProviderErrorKind | None]:
        lock_key = self._refresh_lock_key(cache_key)
        token = self.cache.acquire_lock(lock_key, ttl_seconds=self._refresh_lock_ttl_seconds())
        if token:
            try:
                cached = self.cache.get_json(cache_key)
                if cached:
                    return self._with_cache_metadata(cached, retrieved_at, cache_hit=True), None
                return self._fetch_and_cache(cache_key, location, params, retrieved_at)
            finally:
                self.cache.release_lock(lock_key, token)

        coalesced = self._wait_for_coalesced_cache(cache_key, retrieved_at)
        if coalesced:
            return coalesced, None
        fallback = self._cached_fallback_payload(self._cached_fallback_candidate(cache_key), retrieved_at, ProviderErrorKind.PROVIDER_UNAVAILABLE)
        if fallback:
            return fallback, ProviderErrorKind.PROVIDER_UNAVAILABLE
        return self._unavailable_payload(location, retrieved_at, params, ProviderErrorKind.PROVIDER_UNAVAILABLE), ProviderErrorKind.PROVIDER_UNAVAILABLE

    def _fetch_and_cache(
        self,
        cache_key: str,
        location: dict[str, Any],
        params: dict[str, Any],
        retrieved_at: str,
    ) -> tuple[dict[str, Any], ProviderErrorKind | None]:
        fallback_cached = self._cached_fallback_candidate(cache_key)
        try:
            raw = self._fetch_open_meteo(params)
            normalized = self._normalize(raw, location, retrieved_at, params)
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            error_kind = classify_provider_error(exc, status_code)
            logger.warning(
                "weather_provider_unavailable provider=%s region_id=%s error_kind=%s error_type=%s",
                self.provider,
                location.get("region_id"),
                error_kind.value,
                exc.__class__.__name__,
            )
            fallback = self._cached_fallback_payload(fallback_cached, retrieved_at, error_kind)
            if fallback:
                return fallback, error_kind
            unavailable = self._unavailable_payload(location, retrieved_at, params, error_kind)
            self._cache_transient_unavailable(cache_key, unavailable, error_kind, exc)
            return unavailable, error_kind

        self.cache.set_json(cache_key, normalized, ttl_seconds=self.settings.weather_cache_seconds)
        self.cache.set_json(self._fallback_cache_key(cache_key), normalized, ttl_seconds=self._fallback_cache_ttl_seconds())
        return normalized, None

    def debug_for_region(self, region_id: str | None = None) -> dict[str, Any]:
        weather = self.weather_for_region(region_id=region_id)
        current = weather.get("current") or {}
        return {
            "status": weather.get("status"),
            "data_status": weather.get("data_status"),
            "provider": weather.get("provider"),
            "provider_type": weather.get("provider_type"),
            "coordinates": weather.get("location"),
            "coordinate_method": weather.get("location", {}).get("coordinate_method"),
            "displayed_variable": weather.get("displayed_variable"),
            "raw_provider_timestamp": current.get("raw_provider_timestamp"),
            "local_timestamp": current.get("observed_at"),
            "timestamp_analysis": weather.get("timestamp_analysis"),
            "retrieved_at": weather.get("retrieved_at"),
            "temperature": current.get("temperature"),
            "humidity": current.get("humidity"),
            "wind": current.get("wind_speed"),
            "cache": weather.get("cache"),
            "api_response_status": weather.get("status"),
            "source": weather.get("source"),
            "request": weather.get("request"),
            "quality": weather.get("quality"),
            "provenance": weather.get("provenance"),
        }

    def comparison(
        self,
        region_id: str | None = None,
        reference_temperature: float | None = None,
        reference_humidity: float | None = None,
        reference_wind_speed: float | None = None,
        reference_rainfall: float | None = None,
        reference_source: str = "Google Weather reference",
    ) -> dict[str, Any]:
        weather = self.weather_for_region(region_id=region_id)
        current = weather.get("current") or {}

        def compare(field: str, reference: float | None, warning: float, investigate: float) -> dict[str, Any]:
            application_value = current.get(field)
            difference = round(application_value - reference, 2) if application_value is not None and reference is not None else None
            return {
                "application": application_value,
                "reference": reference,
                "difference": difference,
                "quality": self._difference_quality(difference, warning, investigate),
            }

        return {
            "status": weather.get("status"),
            "data_status": weather.get("data_status"),
            "application_provider": self.provider,
            "application_provider_type": self.provider_type.value,
            "reference_source": reference_source,
            "timestamp": current.get("observed_at"),
            "coordinates": weather.get("location"),
            "thresholds": self._difference_thresholds(),
            "metrics": {
                "temperature": compare(
                    "temperature",
                    reference_temperature,
                    self.settings.weather_temperature_difference_warning_c,
                    self.settings.weather_temperature_difference_investigate_c,
                ),
                "humidity": compare(
                    "humidity",
                    reference_humidity,
                    self.settings.weather_humidity_difference_warning_percent,
                    self.settings.weather_humidity_difference_investigate_percent,
                ),
                "wind_speed": compare(
                    "wind_speed",
                    reference_wind_speed,
                    self.settings.weather_wind_difference_warning_kmh,
                    self.settings.weather_wind_difference_investigate_kmh,
                ),
                "rainfall": compare(
                    "rainfall",
                    reference_rainfall,
                    self.settings.weather_rainfall_difference_warning_mm,
                    self.settings.weather_rainfall_difference_investigate_mm,
                ),
            },
            "note": (
                "Provider differences can occur because of different weather models, observation stations, "
                "interpolation methods, update times, and coordinates. Large discrepancies should be investigated."
            ),
        }

    def _forecast_url(self) -> str:
        return urljoin(self.settings.weather_api_base_url.rstrip("/") + "/", "forecast")

    def _params(self, location: dict[str, Any], forecast_days: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timezone": location["timezone"],
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "forecast_days": max(1, min(forecast_days, 7)),
            "current": ",".join(CURRENT_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "daily": ",".join(DAILY_VARIABLES),
        }
        if self.settings.weather_api_key:
            params["apikey"] = self.settings.weather_api_key
        return params

    def _cache_key(self, params: dict[str, Any]) -> str:
        encoded = "|".join(f"{key}={params[key]}" for key in sorted(params) if key != "apikey")
        return "weather:open-meteo:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _fallback_cache_key(self, cache_key: str) -> str:
        return f"{cache_key}:fallback"

    def _refresh_lock_key(self, cache_key: str) -> str:
        return f"{cache_key}:refresh-lock"

    def _local_lock(self, cache_key: str) -> Lock:
        with self._local_locks_guard:
            lock = self._local_locks.get(cache_key)
            if lock is None:
                lock = Lock()
                self._local_locks[cache_key] = lock
            return lock

    def _refresh_lock_ttl_seconds(self) -> int:
        request_budget = max(1, int(self.settings.weather_request_timeout * MAX_PROVIDER_ATTEMPTS))
        backoff_budget = max(1, int(RETRY_BACKOFF_SECONDS * max(0, MAX_PROVIDER_ATTEMPTS - 1)))
        return request_budget + backoff_budget + 5

    def _fallback_cache_ttl_seconds(self) -> int:
        return max(self.settings.weather_cache_seconds, self.settings.weather_stale_minutes * 60)

    def _cached_fallback_candidate(self, cache_key: str) -> dict[str, Any] | None:
        return self.cache.get_json(self._fallback_cache_key(cache_key)) or self.cache.get_json(cache_key, include_expired=True)

    def _wait_for_coalesced_cache(self, cache_key: str, retrieved_at: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + COALESCED_WAIT_SECONDS
        while time.monotonic() < deadline:
            cached = self.cache.get_json(cache_key)
            if cached:
                return self._with_cache_metadata(cached, retrieved_at, cache_hit=True)
            fallback = self._cached_fallback_candidate(cache_key)
            if fallback:
                return self._cached_fallback_payload(fallback, retrieved_at, ProviderErrorKind.PROVIDER_UNAVAILABLE)
            time.sleep(COALESCED_POLL_SECONDS)
        return None

    def _fetch_open_meteo(self, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(MAX_PROVIDER_ATTEMPTS):
            try:
                response = self.client.get(self._forecast_url(), params=params, timeout=self.settings.weather_request_timeout)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                error_kind = classify_provider_error(exc, status_code)
                if error_kind not in RETRIABLE_PROVIDER_ERRORS or attempt == MAX_PROVIDER_ATTEMPTS - 1:
                    raise
                time.sleep(RETRY_BACKOFF_SECONDS)
        raise last_error or WeatherProviderError("Open-Meteo request failed")

    def _cached_fallback_payload(self, cached: dict[str, Any] | None, retrieved_at: str, error_kind: ProviderErrorKind) -> dict[str, Any] | None:
        if error_kind not in TRANSIENT_PROVIDER_ERRORS or not cached:
            return None
        payload = self._with_cache_metadata(cached, retrieved_at, cache_hit=True)
        usable_statuses = {
            DataQualityStatus.CACHED.value,
            DataQualityStatus.RECENT.value,
            DataQualityStatus.STALE.value,
        }
        if payload.get("status") != "ok" or "current" not in payload or payload["data_status"] not in usable_statuses:
            return None
        payload["message"] = f"Using cached Open-Meteo weather because live provider returned {error_kind.value}."
        payload["cache"]["fallback_reason"] = error_kind.value
        payload["cache"]["fallback"] = True
        payload["provenance"]["quality_status"] = payload["data_status"]
        payload.setdefault("quality", {})["status"] = payload["data_status"]
        return payload

    def _cache_transient_unavailable(self, cache_key: str, payload: dict[str, Any], error_kind: ProviderErrorKind, exc: Exception) -> None:
        if error_kind not in TRANSIENT_PROVIDER_ERRORS:
            return
        self.cache.set_json(cache_key, payload, ttl_seconds=self._transient_error_cache_ttl_seconds(error_kind, exc))

    def _transient_error_cache_ttl_seconds(self, error_kind: ProviderErrorKind, exc: Exception) -> int:
        if error_kind == ProviderErrorKind.RATE_LIMITED:
            retry_after = self._retry_after_seconds(exc)
            if retry_after is not None:
                return max(1, min(retry_after, MAX_ERROR_CACHE_SECONDS))
            return RATE_LIMIT_COOLDOWN_SECONDS
        return TRANSIENT_ERROR_COOLDOWN_SECONDS

    def _retry_after_seconds(self, exc: Exception) -> int | None:
        response = getattr(exc, "response", None)
        retry_after = getattr(response, "headers", {}).get("retry-after") if response is not None else None
        if not retry_after:
            return None
        try:
            return int(float(retry_after))
        except ValueError:
            return None

    def _unavailable_payload(
        self,
        location: dict[str, Any],
        retrieved_at: str,
        params: dict[str, Any],
        error_kind: ProviderErrorKind,
    ) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "data_status": DataQualityStatus.UNAVAILABLE.value,
            "provider": self.provider,
            "provider_type": self.provider_type.value,
            "source": self._forecast_url(),
            "source_type": self.source_type,
            "message": "Live weather data is temporarily unavailable",
            "error": error_kind.value,
            "location": location,
            "retrieved_at": retrieved_at,
            "provenance": DataProvenance(
                provider=self.provider,
                provider_type=self.provider_type,
                source_type=self.source_type,
                source_url=self._forecast_url(),
                retrieved_at=datetime.fromisoformat(retrieved_at),
                region_id=location["region_id"],
                quality_status=DataQualityStatus.UNAVAILABLE,
            ).to_dict(),
            "cache": {"status": "miss", "age_seconds": 0, "ttl_seconds": self.settings.weather_cache_seconds},
            "request": self._request_debug(params),
        }

    def _normalize(self, raw: dict[str, Any], location: dict[str, Any], retrieved_at: str, params: dict[str, Any]) -> dict[str, Any]:
        current = raw.get("current") or {}
        current_units = raw.get("current_units") or {}
        hourly = raw.get("hourly") or {}
        daily = raw.get("daily") or {}
        current_record = self._current_record(current)
        timestamp_analysis = self._timestamp_analysis(current.get("time"), retrieved_at, location["timezone"])
        units = {
            "temperature": current_units.get("temperature_2m", CANONICAL_UNITS["temperature"]),
            "humidity": current_units.get("relative_humidity_2m", CANONICAL_UNITS["humidity"]),
            "wind_speed": current_units.get("wind_speed_10m", CANONICAL_UNITS["wind_speed"]),
            "rainfall": current_units.get("rain", CANONICAL_UNITS["rainfall"]),
            "pressure": current_units.get("surface_pressure", CANONICAL_UNITS["pressure"]),
            "cloud_cover": current_units.get("cloud_cover", CANONICAL_UNITS["cloud_cover"]),
        }
        quality_flags = self._quality_flags(current_record, location, timestamp_analysis, units)
        data_status = self._data_status(quality_flags, timestamp_analysis["observation_age_minutes"], cache_hit=False)
        fire_weather_risk_index = self.engine.calculate_fire_weather_index(
            current_record["temperature"],
            current_record["humidity"],
            current_record["wind_speed"],
            current_record["rainfall"],
        )

        return {
            "status": "ok",
            "data_status": data_status,
            "provider": self.provider,
            "provider_type": self.provider_type.value,
            "source": self._forecast_url(),
            "source_type": self.source_type,
            "location": location,
            "displayed_variable": {
                "field": "temperature",
                "provider_variable": "temperature_2m",
                "description": "Air temperature at 2 meters above ground from Open-Meteo current conditions.",
            },
            "units": units,
            "current": {
                **current_record,
                "raw_provider_timestamp": current.get("time"),
                "observed_at": current.get("time"),
                "retrieved_at": retrieved_at,
                "provider": self.provider,
                "source_type": self.source_type,
                "fire_weather_risk_index": fire_weather_risk_index,
                "metric_label": "Fire Weather Risk Index",
            },
            "hourly": self._series(hourly),
            "daily": self._series(daily),
            "timestamp_analysis": timestamp_analysis,
            "quality": {"valid": not quality_flags, "flags": quality_flags, "status": data_status},
            "provenance": DataProvenance(
                provider=self.provider,
                provider_type=self.provider_type,
                source_type=self.source_type,
                source_url=self._forecast_url(),
                observed_at=datetime.fromisoformat(timestamp_analysis["provider_local_time"]) if timestamp_analysis["provider_local_time"] else None,
                retrieved_at=datetime.fromisoformat(retrieved_at),
                region_id=location["region_id"],
                quality_status=DataQualityStatus(data_status),
            ).to_dict(),
            "cache": {"status": "miss", "age_seconds": 0, "ttl_seconds": self.settings.weather_cache_seconds},
            "request": self._request_debug(params),
            "retrieved_at": retrieved_at,
        }

    def _current_record(self, current: dict[str, Any]) -> dict[str, Any]:
        return {
            "temperature": self._number(current.get("temperature_2m")),
            "apparent_temperature": self._number(current.get("apparent_temperature")),
            "humidity": self._number(current.get("relative_humidity_2m")),
            "wind_speed": self._number(current.get("wind_speed_10m")),
            "wind_direction": self._number(current.get("wind_direction_10m")),
            "wind_gusts": self._number(current.get("wind_gusts_10m")),
            "rainfall": self._number(current.get("rain", current.get("precipitation"))),
            "precipitation": self._number(current.get("precipitation")),
            "pressure": self._number(current.get("surface_pressure")),
            "cloud_cover": self._number(current.get("cloud_cover")),
        }

    def _series(self, payload: dict[str, list[Any]]) -> list[dict[str, Any]]:
        times = payload.get("time") or []
        rows: list[dict[str, Any]] = []
        for index, timestamp in enumerate(times):
            row = {"time": timestamp}
            for key, values in payload.items():
                if key == "time":
                    continue
                if isinstance(values, list) and index < len(values):
                    row[key] = values[index]
            rows.append(row)
        return rows

    def _quality_flags(
        self,
        current: dict[str, Any],
        location: dict[str, Any],
        timestamp_analysis: dict[str, Any] | None = None,
        units: dict[str, str] | None = None,
    ) -> list[str]:
        flags: list[str] = []
        if not -90 <= location["latitude"] <= 90 or not -180 <= location["longitude"] <= 180:
            flags.append("invalid_coordinates")
        flags.extend(validate_canonical_units(units or {}))
        if not -60 <= current["temperature"] <= 70:
            flags.append("temperature_out_of_range")
        if not 0 <= current["humidity"] <= 100:
            flags.append("humidity_out_of_range")
        if current["wind_speed"] < 0:
            flags.append("wind_speed_negative")
        if current["rainfall"] < 0:
            flags.append("rainfall_negative")
        if current["cloud_cover"] is not None and not 0 <= current["cloud_cover"] <= 100:
            flags.append("cloud_cover_out_of_range")
        observation_age = (timestamp_analysis or {}).get("observation_age_minutes")
        if observation_age is not None and observation_age < -15:
            flags.append("provider_timestamp_in_future")
        return flags

    def _timestamp_analysis(self, raw_provider_timestamp: str | None, retrieved_at: str, timezone_name: str) -> dict[str, Any]:
        retrieved_utc = datetime.fromisoformat(retrieved_at)
        local_zone = ZoneInfo(timezone_name)
        app_local_time = retrieved_utc.astimezone(local_zone)
        provider_local_time = None
        observation_age_minutes = None
        if raw_provider_timestamp:
            provider_local_time = datetime.fromisoformat(raw_provider_timestamp).replace(tzinfo=local_zone)
            observation_age_minutes = round((app_local_time - provider_local_time).total_seconds() / 60, 1)
        return {
            "provider_local_time": provider_local_time.isoformat() if provider_local_time else None,
            "retrieved_at_utc": retrieved_utc.isoformat(),
            "application_local_time": app_local_time.isoformat(),
            "timezone": timezone_name,
            "observation_age_minutes": observation_age_minutes,
        }

    def _data_status(self, quality_flags: list[str], observation_age_minutes: float | None, cache_hit: bool) -> str:
        retrieved_at = datetime.now(timezone.utc)
        observed_at = None
        if observation_age_minutes is not None:
            observed_at = retrieved_at - timedelta(minutes=observation_age_minutes)
        policy = FreshnessPolicy.from_settings(self.settings)
        return classify_freshness(
            observed_at,
            retrieved_at,
            policy.weather_max_age,
            policy.weather_recent,
            cache_hit=cache_hit,
            quality_flags=quality_flags,
        ).value

    def _request_debug(self, params: dict[str, Any]) -> dict[str, Any]:
        safe_params = {key: value for key, value in params.items() if key != "apikey"}
        return {"url": self._forecast_url(), "params": safe_params}

    def _difference_quality(self, difference: float | None, warning: float, investigate: float) -> str:
        if difference is None:
            return "not_compared"
        absolute = abs(difference)
        if absolute >= investigate:
            return "investigation_required"
        if absolute >= warning:
            return "warning"
        return "informational"

    def _difference_thresholds(self) -> dict[str, dict[str, float]]:
        return {
            "temperature_c": {
                "warning": self.settings.weather_temperature_difference_warning_c,
                "investigation_required": self.settings.weather_temperature_difference_investigate_c,
            },
            "humidity_percent": {
                "warning": self.settings.weather_humidity_difference_warning_percent,
                "investigation_required": self.settings.weather_humidity_difference_investigate_percent,
            },
            "wind_speed_kmh": {
                "warning": self.settings.weather_wind_difference_warning_kmh,
                "investigation_required": self.settings.weather_wind_difference_investigate_kmh,
            },
            "rainfall_mm": {
                "warning": self.settings.weather_rainfall_difference_warning_mm,
                "investigation_required": self.settings.weather_rainfall_difference_investigate_mm,
            },
        }

    def _number(self, value: Any) -> float:
        if value is None:
            raise WeatherProviderError("Provider response is missing a required weather value")
        return round(float(value), 2)

    def _with_cache_metadata(self, cached: dict[str, Any], retrieved_at: str, cache_hit: bool) -> dict[str, Any]:
        cached_retrieved = cached.get("retrieved_at")
        age_seconds = 0
        if cached_retrieved:
            try:
                age_seconds = max(0, int((datetime.fromisoformat(retrieved_at) - datetime.fromisoformat(cached_retrieved)).total_seconds()))
            except ValueError:
                age_seconds = 0
        cached["cache"] = {
            "status": "hit" if cache_hit else "miss",
            "age_seconds": age_seconds,
            "ttl_seconds": self.settings.weather_cache_seconds,
        }
        current = cached.get("current") or {}
        location = cached.get("location") or {}
        if cached.get("status") != "ok" or not current:
            data_status = cached.get("data_status") or DataQualityStatus.UNAVAILABLE.value
            cached["data_status"] = data_status
            cached.setdefault("quality", {})["status"] = data_status
            if cached.get("provenance"):
                cached["provenance"]["quality_status"] = data_status
            return cached
        if current.get("raw_provider_timestamp") and location.get("timezone"):
            cached["timestamp_analysis"] = self._timestamp_analysis(current.get("raw_provider_timestamp"), retrieved_at, location["timezone"])
        cached["data_status"] = self._data_status(
            cached.get("quality", {}).get("flags", []),
            cached.get("timestamp_analysis", {}).get("observation_age_minutes"),
            cache_hit=True,
        )
        cached.setdefault("quality", {})["status"] = cached["data_status"]
        return cached
