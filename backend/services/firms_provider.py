from __future__ import annotations

import csv
import hashlib
import io
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any
from urllib.parse import quote

import httpx

from backend.core.config import Settings, get_settings
from backend.services.environmental_foundation import (
    DataQualityStatus,
    ProviderErrorKind,
    ProviderName,
    ProviderRequestMetadata,
    ProviderType,
    classify_provider_error,
    provider_operation_completed,
    provider_operation_started,
    validate_measurement_ranges,
)
from backend.services.region_registry import RegionLocation, get_region_location

SUPPORTED_FIRMS_PRODUCTS = {
    "MODIS_NRT",
    "MODIS_SP",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_NRT",
    "VIIRS_SNPP_NRT",
    "VIIRS_SNPP_SP",
}

REQUIRED_COLUMNS = {"latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument", "confidence"}


@dataclass(frozen=True)
class FIRMSProviderError:
    kind: ProviderErrorKind
    message: str
    status_code: int | None = None


@dataclass(frozen=True)
class NormalizedFIRMSHotspot:
    region_id: str
    database_region_id: int
    latitude: float
    longitude: float
    detected_at: datetime
    retrieved_at: datetime
    satellite: str
    instrument: str
    confidence: float
    severity: str
    product: str
    provider: str
    source_record_id: str
    quality_status: DataQualityStatus
    brightness: float | None = None
    frp: float | None = None
    scan: float | None = None
    track: float | None = None
    daynight: str | None = None
    provenance_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FIRMSProviderResult:
    status: DataQualityStatus
    provider: str
    product: str
    region_id: str
    retrieved_at: datetime
    source_url: str | None = None
    records: list[NormalizedFIRMSHotspot] = field(default_factory=list)
    records_received: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    invalid_records: list[dict[str, Any]] = field(default_factory=list)
    error: FIRMSProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status != DataQualityStatus.UNAVAILABLE


class FIRMSProvider:
    provider = ProviderName.NASA_FIRMS.value
    provider_type = ProviderType.HOTSPOT

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self.client = client

    def fetch_active_fires(self, region_id: str, lookback_hours: int | None = None, product: str | None = None) -> FIRMSProviderResult:
        region = get_region_location(region_id)
        selected_product = (product or self.settings.firms_product).strip()
        selected_lookback = lookback_hours or self.settings.firms_lookback_hours
        retrieved_at = datetime.now(timezone.utc)
        metadata = ProviderRequestMetadata(
            provider=self.provider,
            provider_type=self.provider_type,
            operation="fetch_active_fires",
            region_id=region.id,
            request={"product": selected_product, "lookback_hours": selected_lookback},
        )
        started = provider_operation_started(metadata)

        config_error = self._configuration_error(selected_product, selected_lookback)
        if config_error:
            provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=config_error.kind)
            return FIRMSProviderResult(
                status=DataQualityStatus.UNAVAILABLE,
                provider=self.provider,
                product=selected_product,
                region_id=region.id,
                retrieved_at=retrieved_at,
                error=config_error,
            )

        url = self._area_csv_url(region, selected_product, selected_lookback)
        redacted_url = self._redacted_area_csv_url(url)
        try:
            response = self._get_with_retries(url)
            if response.status_code >= 400:
                error_kind = classify_provider_error(status_code=response.status_code)
                provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=error_kind)
                return FIRMSProviderResult(
                    status=DataQualityStatus.UNAVAILABLE,
                    provider=self.provider,
                    product=selected_product,
                    region_id=region.id,
                    retrieved_at=retrieved_at,
                    source_url=redacted_url,
                    error=FIRMSProviderError(error_kind, f"FIRMS returned HTTP {response.status_code}.", response.status_code),
                )
            result = self._parse_response(response.text, region, selected_product, selected_lookback, retrieved_at, redacted_url)
            provider_operation_completed(metadata, started, result.status, record_count=result.records_valid, error_kind=result.error.kind if result.error else None)
            return result
        except Exception as exc:
            error_kind = classify_provider_error(exc)
            provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=error_kind)
            return FIRMSProviderResult(
                status=DataQualityStatus.UNAVAILABLE,
                provider=self.provider,
                product=selected_product,
                region_id=region.id,
                retrieved_at=retrieved_at,
                source_url=redacted_url,
                error=FIRMSProviderError(error_kind, str(exc)),
            )

    def _configuration_error(self, product: str, lookback_hours: int) -> FIRMSProviderError | None:
        if not self.settings.firms_enabled:
            return FIRMSProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "FIRMS ingestion is disabled by FIRMS_ENABLED.")
        if not self.settings.firms_map_key:
            return FIRMSProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "FIRMS_ENABLED is true but FIRMS_MAP_KEY is not configured.")
        if product not in SUPPORTED_FIRMS_PRODUCTS:
            return FIRMSProviderError(ProviderErrorKind.CONFIGURATION_ERROR, f"Unsupported FIRMS product: {product}.")
        if lookback_hours <= 0:
            return FIRMSProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "FIRMS_LOOKBACK_HOURS must be greater than zero.")
        if self._day_range(lookback_hours) > 5:
            return FIRMSProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "FIRMS Area API day range is limited to 1..5 days.")
        return None

    def _day_range(self, lookback_hours: int) -> int:
        return max(1, min(5, ceil(lookback_hours / 24)))

    def _area_csv_url(self, region: RegionLocation, product: str, lookback_hours: int) -> str:
        bbox = ",".join(f"{value:.5f}".rstrip("0").rstrip(".") for value in region.bounding_box(self.settings.firms_region_buffer_degrees))
        base_url = self.settings.firms_base_url.rstrip("/")
        map_key = quote(self.settings.firms_map_key or "", safe="")
        area = quote(bbox, safe=",.-")
        return f"{base_url}/area/csv/{map_key}/{quote(product, safe='')}/{area}/{self._day_range(lookback_hours)}"

    def _redacted_area_csv_url(self, url: str) -> str:
        map_key = quote(self.settings.firms_map_key or "", safe="")
        if not map_key:
            return url
        return url.replace(f"/area/csv/{map_key}/", "/area/csv/<redacted>/", 1)

    def _get_with_retries(self, url: str) -> httpx.Response:
        attempts = max(1, self.settings.firms_retry_attempts + 1)
        last_response: httpx.Response | None = None
        last_error: Exception | None = None
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=self.settings.firms_request_timeout)
        try:
            for attempt in range(attempts):
                try:
                    response = client.get(url, timeout=self.settings.firms_request_timeout)
                    last_response = response
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        return response
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self.settings.firms_retry_backoff_seconds * (2**attempt))
            if last_response is not None:
                return last_response
            if last_error is not None:
                raise last_error
            raise RuntimeError("FIRMS request failed without response.")
        finally:
            if own_client:
                client.close()

    def _parse_response(
        self,
        text: str,
        region: RegionLocation,
        product: str,
        lookback_hours: int,
        retrieved_at: datetime,
        source_url: str,
    ) -> FIRMSProviderResult:
        if text.startswith("Invalid MAP_KEY"):
            return self._error_result(region, product, retrieved_at, source_url, ProviderErrorKind.AUTHENTICATION_ERROR, "FIRMS rejected the configured MAP_KEY.")
        if text.startswith("Invalid source") or text.startswith("Invalid day range"):
            return self._error_result(region, product, retrieved_at, source_url, ProviderErrorKind.CONFIGURATION_ERROR, text.strip())

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return self._error_result(region, product, retrieved_at, source_url, ProviderErrorKind.INVALID_RESPONSE, "FIRMS response did not contain a CSV header.")
        missing = REQUIRED_COLUMNS.difference(set(reader.fieldnames))
        if missing:
            return self._error_result(region, product, retrieved_at, source_url, ProviderErrorKind.INVALID_RESPONSE, f"FIRMS CSV missing required columns: {sorted(missing)}.")

        cutoff = retrieved_at - timedelta(hours=lookback_hours)
        records: list[NormalizedFIRMSHotspot] = []
        invalid_records: list[dict[str, Any]] = []
        rows = list(reader)[: self.settings.firms_max_records]
        west, south, east, north = region.bounding_box(self.settings.firms_region_buffer_degrees)
        for index, row in enumerate(rows):
            try:
                record = self._normalize_row(row, region, product, retrieved_at)
                if record.detected_at < cutoff:
                    continue
                if not (south <= record.latitude <= north and west <= record.longitude <= east):
                    raise ValueError("coordinate outside requested monitoring bounding box")
                records.append(record)
            except Exception as exc:
                invalid_records.append({"row": index + 1, "reason": str(exc)})

        status = DataQualityStatus.SUSPICIOUS if invalid_records else DataQualityStatus.LIVE
        return FIRMSProviderResult(
            status=status,
            provider=self.provider,
            product=product,
            region_id=region.id,
            retrieved_at=retrieved_at,
            source_url=source_url,
            records=records,
            records_received=len(rows),
            records_valid=len(records),
            records_invalid=len(invalid_records),
            invalid_records=invalid_records,
        )

    def _normalize_row(self, row: dict[str, str], region: RegionLocation, product: str, retrieved_at: datetime) -> NormalizedFIRMSHotspot:
        latitude = self._float(row.get("latitude"), "latitude")
        longitude = self._float(row.get("longitude"), "longitude")
        flags = validate_measurement_ranges({"latitude": latitude, "longitude": longitude})
        if flags:
            raise ValueError(", ".join(flags))
        detected_at = self._acquisition_time(row.get("acq_date"), row.get("acq_time"))
        satellite = self._required_text(row.get("satellite"), "satellite")
        instrument = self._required_text(row.get("instrument"), "instrument")
        confidence = self._confidence(row.get("confidence"))
        brightness = self._optional_float(row.get("bright_ti4") or row.get("brightness") or row.get("bright_t31"))
        frp = self._optional_float(row.get("frp"))
        scan = self._optional_float(row.get("scan"))
        track = self._optional_float(row.get("track"))
        daynight = (row.get("daynight") or "").strip() or None
        source_record_id = self._source_record_id(row, product, latitude, longitude, detected_at, satellite, instrument)
        return NormalizedFIRMSHotspot(
            region_id=region.id,
            database_region_id=region.database_id,
            latitude=latitude,
            longitude=longitude,
            detected_at=detected_at,
            retrieved_at=retrieved_at,
            satellite=satellite,
            instrument=instrument,
            confidence=confidence,
            severity=self._severity(confidence, frp),
            product=product,
            provider=self.provider,
            source_record_id=source_record_id,
            quality_status=DataQualityStatus.LIVE,
            brightness=brightness,
            frp=frp,
            scan=scan,
            track=track,
            daynight=daynight,
            provenance_metadata={
                "version": row.get("version"),
                "type": row.get("type"),
                "provider_product": product,
                "row_fields": {key: row.get(key) for key in ("acq_date", "acq_time", "satellite", "instrument", "confidence", "frp", "daynight")},
            },
        )

    def _error_result(
        self,
        region: RegionLocation,
        product: str,
        retrieved_at: datetime,
        source_url: str | None,
        kind: ProviderErrorKind,
        message: str,
    ) -> FIRMSProviderResult:
        return FIRMSProviderResult(
            status=DataQualityStatus.UNAVAILABLE,
            provider=self.provider,
            product=product,
            region_id=region.id,
            retrieved_at=retrieved_at,
            source_url=source_url,
            error=FIRMSProviderError(kind, message),
        )

    def _acquisition_time(self, date_value: str | None, time_value: str | None) -> datetime:
        if not date_value or not time_value:
            raise ValueError("missing acquisition timestamp")
        padded = str(time_value).strip().zfill(4)
        if len(padded) != 4 or not padded.isdigit():
            raise ValueError("invalid acquisition time")
        return datetime.strptime(f"{date_value.strip()} {padded}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)

    def _confidence(self, value: str | None) -> float:
        text = self._required_text(value, "confidence").lower()
        mapped = {"l": 30.0, "low": 30.0, "n": 60.0, "nominal": 60.0, "h": 85.0, "high": 85.0}
        if text in mapped:
            return mapped[text]
        confidence = float(text)
        if confidence < 0 or confidence > 100:
            raise ValueError("confidence outside 0..100")
        return confidence

    def _severity(self, confidence: float, frp: float | None) -> str:
        if confidence >= 85 or (frp is not None and frp >= 50):
            return "Critical"
        if confidence >= 70 or (frp is not None and frp >= 20):
            return "High"
        if confidence >= 40:
            return "Moderate"
        return "Low"

    def _source_record_id(self, row: dict[str, str], product: str, latitude: float, longitude: float, detected_at: datetime, satellite: str, instrument: str) -> str:
        parts = [
            self.provider,
            product,
            satellite,
            instrument,
            detected_at.isoformat(),
            f"{latitude:.5f}",
            f"{longitude:.5f}",
            str(row.get("frp") or ""),
            str(row.get("version") or ""),
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    def _float(self, value: str | None, field_name: str) -> float:
        if value is None or str(value).strip() == "":
            raise ValueError(f"missing {field_name}")
        return float(value)

    def _optional_float(self, value: str | None) -> float | None:
        if value is None or str(value).strip() == "":
            return None
        return float(value)

    def _required_text(self, value: str | None, field_name: str) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError(f"missing {field_name}")
        return str(value).strip()
