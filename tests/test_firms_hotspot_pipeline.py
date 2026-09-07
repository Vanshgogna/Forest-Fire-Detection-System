from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import Settings
from backend.database.models import Base
from backend.schemas.environmental import CanonicalHotspotData
from backend.services.environmental_data_service import EnvironmentalDataService
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind
from backend.services.firms_provider import FIRMSProvider
from backend.services.hotspot_aggregation_service import HotspotAggregationService
from backend.services.hotspot_ingestion_service import FIRMSIngestionService


def _settings(**overrides):
    values = {
        "firms_enabled": True,
        "firms_map_key": "test-map-key",
        "firms_base_url": "https://firms.modaps.eosdis.nasa.gov/api",
        "firms_product": "VIIRS_SNPP_NRT",
        "firms_lookback_hours": 24,
        "firms_max_records": 500,
        "firms_request_timeout": 0.1,
        "firms_retry_attempts": 0,
        "firms_retry_backoff_seconds": 0,
        "database_url": "sqlite+pysqlite:///:memory:",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _csv(rows: str) -> str:
    return "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,frp,daynight\n" + rows


def _current_row(**overrides) -> str:
    now = datetime.now(timezone.utc)
    values = {
        "latitude": "11.667",
        "longitude": "76.629",
        "bright_ti4": "334.4",
        "scan": "0.5",
        "track": "0.4",
        "acq_date": now.date().isoformat(),
        "acq_time": now.strftime("%H%M"),
        "satellite": "N",
        "instrument": "VIIRS",
        "confidence": "h",
        "version": "2.0NRT",
        "frp": "42.1",
        "daynight": "D",
    }
    values.update(overrides)
    return ",".join(values[key] for key in values)


def _provider_for_response(body: str, status_code: int = 200, settings: Settings | None = None) -> FIRMSProvider:
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, text=body, request=request))
    return FIRMSProvider(settings=settings or _settings(), client=httpx.Client(transport=transport))


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_firms_provider_builds_area_csv_request_and_normalizes_viirs_rows():
    provider = _provider_for_response(_csv(_current_row()))

    result = provider.fetch_active_fires("r1")

    assert result.ok is True
    assert result.product == "VIIRS_SNPP_NRT"
    assert "/area/csv/<redacted>/VIIRS_SNPP_NRT/" in (result.source_url or "")
    assert "test-map-key" not in (result.source_url or "")
    assert "76.129" in (result.source_url or "")
    assert result.records_received == 1
    assert result.records_valid == 1
    record = result.records[0]
    assert record.provider == "nasa-firms"
    assert record.source_record_id
    assert record.latitude == 11.667
    assert record.longitude == 76.629
    assert record.confidence == 85.0
    assert record.severity == "Critical"
    assert record.detected_at.tzinfo is not None


def test_firms_provider_rejects_invalid_coordinates_and_timestamps():
    rows = _current_row(latitude="99") + "\n" + _current_row(acq_time="bad")
    provider = _provider_for_response(_csv(rows))

    result = provider.fetch_active_fires("r1")

    assert result.status == DataQualityStatus.SUSPICIOUS
    assert result.records_valid == 0
    assert result.records_invalid == 2


def test_firms_provider_allows_missing_optional_thermal_fields():
    provider = _provider_for_response(_csv(_current_row(bright_ti4="", frp="", scan="", track="")))

    result = provider.fetch_active_fires("r1")

    assert result.records_valid == 1
    assert result.records[0].brightness is None
    assert result.records[0].frp is None


def test_firms_provider_reports_missing_map_key_without_http_call():
    provider = FIRMSProvider(settings=_settings(firms_map_key=None), client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))))

    result = provider.fetch_active_fires("r1")

    assert result.status == DataQualityStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.kind == ProviderErrorKind.CONFIGURATION_ERROR


def test_firms_provider_handles_http_rate_limit_and_timeout():
    rate_limited = _provider_for_response("rate limited", status_code=429)
    timeout_transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.TimeoutException("timeout", request=request)))
    timed_out = FIRMSProvider(settings=_settings(), client=httpx.Client(transport=timeout_transport))

    rate_result = rate_limited.fetch_active_fires("r1")
    timeout_result = timed_out.fetch_active_fires("r1")

    assert rate_result.error is not None
    assert rate_result.error.kind == ProviderErrorKind.RATE_LIMITED
    assert timeout_result.error is not None
    assert timeout_result.error.kind == ProviderErrorKind.TIMEOUT


def test_zero_hotspots_are_available_not_unavailable_after_ingestion():
    db = _session()
    provider = _provider_for_response(_csv(""))

    result = FIRMSIngestionService(db, provider=provider).ingest_regions(["r1"])
    summary = HotspotAggregationService(db, settings=_settings()).summary_for_region("r1")

    assert result.records_received == 0
    assert result.status == DataQualityStatus.LIVE
    assert summary.available is True
    assert summary.count_24h == 0
    assert summary.records == []


def test_firms_ingestion_is_idempotent_and_aggregation_counts_windows():
    db = _session()
    provider = _provider_for_response(_csv(_current_row()))
    service = FIRMSIngestionService(db, provider=provider)

    first = service.ingest_regions(["r1"])
    second = service.ingest_regions(["r1"])
    summary = HotspotAggregationService(db, settings=_settings()).summary_for_region("r1")

    assert first.records_inserted == 1
    assert second.records_inserted == 0
    assert second.duplicates == 1
    assert summary.count_24h == 1
    assert summary.count_48h == 1
    assert summary.count_7d == 1
    assert summary.nearest_hotspot_distance_km == 0


def test_stale_hotspot_summary_uses_hotspot_freshness_threshold():
    db = _session()
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    provider = _provider_for_response(_csv(_current_row(acq_date=old.date().isoformat(), acq_time=old.strftime("%H%M"))), settings=_settings(firms_lookback_hours=120))

    FIRMSIngestionService(db, provider=provider).ingest_regions(["r1"])
    summary = HotspotAggregationService(db, settings=_settings(firms_enabled=True, hotspot_max_age_hours=24)).summary_for_region("r1")

    assert summary.status == DataQualityStatus.STALE


def test_environmental_snapshot_can_include_canonical_hotspot_data(monkeypatch):
    db = _session()
    provider = _provider_for_response(_csv(_current_row()))
    FIRMSIngestionService(db, provider=provider).ingest_regions(["r1"])

    class SessionFactory:
        def __call__(self):
            return db

    monkeypatch.setattr("backend.services.environmental_data_service.SessionLocal", SessionFactory())
    service = EnvironmentalDataService(settings=_settings(), weather_provider=None)

    hotspots = service.get_recent_hotspots("r1")

    assert isinstance(hotspots, CanonicalHotspotData)
    assert hotspots.hotspot_count_24h == 1
    assert hotspots.provider == "nasa-firms"
