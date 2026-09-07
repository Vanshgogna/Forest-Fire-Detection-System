from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from time import perf_counter
from typing import Any, Mapping, Protocol


logger = logging.getLogger("firesight.providers")


class DataMode(str, Enum):
    LIVE = "live"
    SIMULATION = "simulation"


class ProviderType(str, Enum):
    WEATHER = "WEATHER"
    SATELLITE = "SATELLITE"
    HOTSPOT = "HOTSPOT"
    OTHER = "OTHER"


class ProviderName(str, Enum):
    OPEN_METEO = "open-meteo"
    NASA_FIRMS = "nasa-firms"
    SENTINEL_2 = "sentinel-2"
    DEVELOPMENT_FIXTURE = "development-fixture"
    UNKNOWN = "unknown"


class DataQualityStatus(str, Enum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    CACHED = "CACHED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    SUSPICIOUS = "SUSPICIOUS"
    SIMULATED = "SIMULATED"


class ProviderErrorKind(str, Enum):
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    UNKNOWN = "UNKNOWN"


CANONICAL_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "wind_speed": "km/h",
    "rainfall": "mm",
    "precipitation": "mm",
    "pressure": "hPa",
    "cloud_cover": "%",
    "latitude": "degrees",
    "longitude": "degrees",
}


@dataclass(frozen=True)
class ProviderRequestMetadata:
    provider: str
    provider_type: ProviderType
    operation: str
    region_id: str | None = None
    request: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderResponseMetadata:
    provider: str
    provider_type: ProviderType
    retrieved_at: datetime
    status: DataQualityStatus
    error_kind: ProviderErrorKind | None = None
    record_count: int = 0


class EnvironmentalProvider(Protocol):
    provider: str
    provider_type: ProviderType

    def fetch(self, request: ProviderRequestMetadata) -> Any:
        """Fetch data from an external provider and return normalized metadata."""


@dataclass(frozen=True)
class DataProvenance:
    provider: str
    provider_type: ProviderType
    source_type: str
    region_id: str
    quality_status: DataQualityStatus
    retrieved_at: datetime
    observed_at: datetime | None = None
    acquired_at: datetime | None = None
    source_record_id: str | None = None
    source_url: str | None = None
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_type": self.provider_type.value,
            "source_type": self.source_type,
            "source_record_id": self.source_record_id,
            "source_url": self.source_url,
            "observed_at": self._iso(self.observed_at),
            "acquired_at": self._iso(self.acquired_at),
            "retrieved_at": self._iso(self.retrieved_at),
            "request_id": self.request_id,
            "region_id": self.region_id,
            "quality_status": self.quality_status.value,
        }

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


@dataclass(frozen=True)
class FreshnessPolicy:
    weather_recent: timedelta
    weather_max_age: timedelta
    vegetation_max_age: timedelta
    hotspot_max_age: timedelta

    @classmethod
    def from_settings(cls, settings: Any) -> "FreshnessPolicy":
        return cls(
            weather_recent=timedelta(minutes=settings.weather_recent_minutes),
            weather_max_age=timedelta(minutes=settings.weather_stale_minutes),
            vegetation_max_age=timedelta(days=settings.vegetation_max_age_days),
            hotspot_max_age=timedelta(hours=settings.hotspot_max_age_hours),
        )


def ensure_aware_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_freshness(
    observed_at: datetime | str | None,
    retrieved_at: datetime | str | None,
    max_age: timedelta,
    recent_age: timedelta | None = None,
    *,
    cache_hit: bool = False,
    simulated: bool = False,
    unavailable: bool = False,
    quality_flags: list[str] | None = None,
) -> DataQualityStatus:
    if simulated:
        return DataQualityStatus.SIMULATED
    if unavailable:
        return DataQualityStatus.UNAVAILABLE
    if quality_flags:
        return DataQualityStatus.SUSPICIOUS

    observed = ensure_aware_utc(observed_at)
    retrieved = ensure_aware_utc(retrieved_at)
    if observed is None or retrieved is None:
        return DataQualityStatus.SUSPICIOUS
    if observed - retrieved > timedelta(minutes=15):
        return DataQualityStatus.SUSPICIOUS

    age = retrieved - observed
    if age > max_age:
        return DataQualityStatus.STALE
    if cache_hit:
        return DataQualityStatus.CACHED
    if recent_age is not None and age > recent_age:
        return DataQualityStatus.RECENT
    return DataQualityStatus.LIVE


def validate_canonical_units(units: Mapping[str, str]) -> list[str]:
    mismatches: list[str] = []
    for field, expected in CANONICAL_UNITS.items():
        actual = units.get(field)
        if actual is not None and actual != expected:
            mismatches.append(f"{field}_unit_expected_{expected}")
    return mismatches


def validate_measurement_ranges(values: Mapping[str, float | int | None]) -> list[str]:
    ranges = {
        "temperature": (-60, 70),
        "humidity": (0, 100),
        "wind_speed": (0, None),
        "rainfall": (0, None),
        "precipitation": (0, None),
        "latitude": (-90, 90),
        "longitude": (-180, 180),
        "ndvi": (-1, 1),
        "nbr": (-1, 1),
    }
    flags: list[str] = []
    for field, (minimum, maximum) in ranges.items():
        value = values.get(field)
        if value is None:
            continue
        if minimum is not None and value < minimum:
            flags.append(f"{field}_below_range")
        if maximum is not None and value > maximum:
            flags.append(f"{field}_above_range")
    return flags


def classify_provider_error(error: Exception | None = None, status_code: int | None = None) -> ProviderErrorKind:
    if status_code in {401, 403}:
        return ProviderErrorKind.AUTHENTICATION_ERROR
    if status_code == 429:
        return ProviderErrorKind.RATE_LIMITED
    if status_code is not None and 500 <= status_code <= 599:
        return ProviderErrorKind.PROVIDER_UNAVAILABLE
    if status_code is not None and 400 <= status_code <= 499:
        return ProviderErrorKind.CONFIGURATION_ERROR
    if error is None:
        return ProviderErrorKind.UNKNOWN

    name = error.__class__.__name__.lower()
    if "timeout" in name:
        return ProviderErrorKind.TIMEOUT
    if "validation" in name or "valueerror" in name:
        return ProviderErrorKind.VALIDATION_ERROR
    if "json" in name or "decode" in name:
        return ProviderErrorKind.INVALID_RESPONSE
    if "database" in name or "sql" in name:
        return ProviderErrorKind.DATABASE_ERROR
    if "connect" in name or "network" in name or "http" in name:
        return ProviderErrorKind.PROVIDER_UNAVAILABLE
    return ProviderErrorKind.UNKNOWN


def provider_operation_started(metadata: ProviderRequestMetadata) -> float:
    started = perf_counter()
    logger.info(
        "provider_operation_started provider=%s provider_type=%s operation=%s region_id=%s",
        metadata.provider,
        metadata.provider_type.value,
        metadata.operation,
        metadata.region_id,
    )
    return started


def provider_operation_completed(
    metadata: ProviderRequestMetadata,
    started: float,
    status: DataQualityStatus,
    record_count: int = 0,
    error_kind: ProviderErrorKind | None = None,
) -> None:
    duration_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(
        "provider_operation_completed provider=%s provider_type=%s operation=%s region_id=%s duration_ms=%s status=%s record_count=%s error_kind=%s",
        metadata.provider,
        metadata.provider_type.value,
        metadata.operation,
        metadata.region_id,
        duration_ms,
        status.value,
        record_count,
        error_kind.value if error_kind else None,
    )
