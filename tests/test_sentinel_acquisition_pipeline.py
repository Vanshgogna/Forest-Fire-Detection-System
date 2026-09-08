from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote_plus

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import Settings
from backend.database.models import Base
from backend.repositories.environment import SatelliteImageRepository
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind
from backend.services.region_registry import get_region_location
from backend.services.sentinel_acquisition_service import SentinelAcquisitionService
from backend.services.sentinel_provider import SentinelAcquisitionStatus, SentinelProvider


def _settings(tmp_path: Path | None = None, **overrides):
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "sentinel_enabled": True,
        "copernicus_client_id": "client-id",
        "copernicus_client_secret": "client-secret",
        "copernicus_token_url": "https://identity.example/token",
        "sentinel_base_url": "https://catalogue.example/odata/v1",
        "sentinel_download_url": "https://download.example/odata/v1",
        "sentinel_product_type": "S2MSI2A",
        "sentinel_lookback_days": 14,
        "sentinel_max_cloud_cover": 40,
        "sentinel_request_timeout": 0.1,
        "sentinel_max_scene_size_mb": 1,
        "sentinel_temp_dir": str(tmp_path or Path("/tmp") / "firesight-sentinel-tests"),
        "sentinel_retry_attempts": 0,
        "sentinel_retry_backoff_seconds": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _scene_item(product_id: str, name: str, cloud: float, captured_at: datetime, content_length: int = 7, online: bool = True):
    return {
        "Id": product_id,
        "Name": name,
        "ContentDate": {"Start": captured_at.isoformat().replace("+00:00", "Z"), "End": captured_at.isoformat().replace("+00:00", "Z")},
        "ContentLength": content_length,
        "Online": online,
        "S3Path": f"/eodata/Sentinel-2/{name}.SAFE",
        "GeoFootprint": {"type": "Polygon", "coordinates": []},
        "Checksum": [{"Algorithm": "MD5", "Value": "provider-md5"}],
        "Attributes": [
            {"Name": "cloudCover", "Value": cloud},
            {"Name": "productType", "Value": "S2MSI2A"},
            {"Name": "tileIdentifier", "Value": "43PGP"},
        ],
    }


def _provider_with_transport(handler, tmp_path: Path | None = None, **settings_overrides) -> SentinelProvider:
    return SentinelProvider(settings=_settings(tmp_path, **settings_overrides), client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_sentinel_provider_reports_disabled_without_http_call(tmp_path):
    calls = []
    provider = _provider_with_transport(lambda request: calls.append(request) or httpx.Response(500, request=request), tmp_path, sentinel_enabled=False)

    result = provider.search_scenes("r1")

    assert result.status == DataQualityStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.kind == ProviderErrorKind.CONFIGURATION_ERROR
    assert calls == []


def test_sentinel_provider_builds_copernicus_odata_filter_and_selects_best_scene(tmp_path):
    seen_urls: list[str] = []
    now = datetime.now(timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "value": [
                    _scene_item("older", "S2A_MSIL2A_20260820T050000_N0511_R019_T43PGP_20260820T090000.SAFE", 2, now - timedelta(days=4)),
                    _scene_item("clear", "S2B_MSIL2A_20260828T050000_N0511_R019_T43PGP_20260828T090000.SAFE", 5, now - timedelta(days=1)),
                    _scene_item("cloudy", "S2A_MSIL2A_20260829T050000_N0511_R019_T43PGP_20260829T090000.SAFE", 35, now),
                ]
            },
            request=request,
        )

    result = _provider_with_transport(handler, tmp_path).search_scenes("r1")
    query = unquote_plus(seen_urls[0])

    assert result.ok is True
    assert "Collection/Name eq 'SENTINEL-2'" in query
    assert "productType" in query
    assert "S2MSI2A" in query
    assert "cloudCover" in query
    assert "OData.CSC.Intersects" in query
    assert "POLYGON((76.129" in query
    assert result.selected_scene is not None
    assert result.selected_scene.product_id == "older"
    assert result.selected_scene.product_level == "L2A"
    assert result.selected_scene.platform == "S2A"
    assert result.selected_scene.tile_id == "43PGP"


def test_sentinel_provider_classifies_invalid_catalogue_response(tmp_path):
    provider = _provider_with_transport(lambda request: httpx.Response(200, json={"unexpected": []}, request=request), tmp_path)

    result = provider.search_scenes("r1")

    assert result.status == DataQualityStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.kind == ProviderErrorKind.VALIDATION_ERROR


def test_sentinel_provider_downloads_with_token_cache_checksum_and_size_guard(tmp_path):
    token_calls = 0
    download_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, download_calls
        if request.url.host == "identity.example":
            token_calls += 1
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 600}, request=request)
        download_calls += 1
        assert request.headers["authorization"] == "Bearer token-1"
        return httpx.Response(200, content=b"zipdata", headers={"content-type": "application/zip"}, request=request)

    provider = _provider_with_transport(handler, tmp_path)
    scene = _scene_item("product-1", "S2A_MSIL2A_20260829T050000_N0511_R019_T43PGP_20260829T090000.SAFE", 5, datetime.now(timezone.utc))
    candidate = provider._candidate_from_item(scene, get_region_location("r1"), datetime.now(timezone.utc), "catalogue")

    first = provider.download_scene(candidate, tmp_path)
    second = provider.download_scene(candidate, tmp_path)

    assert first.ok is True
    assert second.ok is True
    assert token_calls == 1
    assert download_calls == 2
    assert first.file_size_bytes == 7
    assert first.checksum == "a1b8b2250981a957cb59f74e9a9eb9f019e94e7e50d28596f6a927112b1ca256"
    assert first.storage_reference is not None
    assert Path(first.storage_reference).exists()
    assert not list((tmp_path / "r1").glob("*.part"))


def test_sentinel_provider_blocks_oversized_scene_before_download(tmp_path):
    provider = _provider_with_transport(lambda request: httpx.Response(500, request=request), tmp_path, sentinel_max_scene_size_mb=0.000001)
    scene = _scene_item("huge", "S2A_MSIL2A_20260829T050000_N0511_R019_T43PGP_20260829T090000.SAFE", 5, datetime.now(timezone.utc), content_length=10_000)
    candidate = provider._candidate_from_item(scene, get_region_location("r1"), datetime.now(timezone.utc), "catalogue")

    result = provider.download_scene(candidate, tmp_path)

    assert result.status == SentinelAcquisitionStatus.FAILED
    assert result.error is not None
    assert result.error.kind == ProviderErrorKind.VALIDATION_ERROR


def test_sentinel_acquisition_persists_provenance_and_is_idempotent(tmp_path):
    request_counts = {"catalogue": 0, "token": 0, "download": 0}
    now = datetime.now(timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "catalogue.example":
            request_counts["catalogue"] += 1
            return httpx.Response(200, json={"value": [_scene_item("product-1", "S2A_MSIL2A_20260829T050000_N0511_R019_T43PGP_20260829T090000.SAFE", 4, now)]}, request=request)
        if request.url.host == "identity.example":
            request_counts["token"] += 1
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 600}, request=request)
        request_counts["download"] += 1
        return httpx.Response(200, content=b"zipdata", headers={"content-type": "application/zip"}, request=request)

    db = _session()
    provider = _provider_with_transport(handler, tmp_path)
    service = SentinelAcquisitionService(db, provider=provider, settings=provider.settings)

    first = service.acquire_latest_scene(["r1"])
    second = service.acquire_latest_scene(["r1"])
    record = SatelliteImageRepository(db).by_product_id("sentinel-2", "product-1")
    status = service.latest_scene_status("r1")

    assert first.acquired == 1
    assert second.reused == 1
    assert request_counts["catalogue"] == 2
    assert request_counts["download"] == 1
    assert record is not None
    assert record.acquisition_status == SentinelAcquisitionStatus.VERIFIED
    assert record.provider == "sentinel-2"
    assert record.metadata_json["source_type"] == "copernicus_odata_products"
    assert record.storage_reference
    assert status["available"] is True
    assert status["product_id"] == "product-1"


def test_sentinel_status_exposes_processed_ndvi_and_nbr(tmp_path):
    db = _session()
    now = datetime.now(timezone.utc)
    provider = _provider_with_transport(
        lambda request: httpx.Response(200, json={"value": [_scene_item("product-1", "S2A_MSIL2A_20260829T050000_N0511_R019_T43PGP_20260829T090000.SAFE", 4, now)]}, request=request),
        tmp_path,
    )
    service = SentinelAcquisitionService(db, provider=provider, settings=provider.settings)
    service.acquire_latest_scene(["r1"], download=False)
    record = SatelliteImageRepository(db).by_product_id("sentinel-2", "product-1")
    record.metadata_json = {
        **(record.metadata_json or {}),
        "ndvi_processing": {
            "status": "READY",
            "quality_status": "LIVE",
            "processing_version": provider.settings.sentinel_ndvi_processing_version,
            "statistics": {"mean": 0.52, "valid_pixel_percentage": 94.0},
            "nbr_statistics": {"mean": 0.31, "valid_pixel_percentage": 93.0},
            "processed_at": now.isoformat(),
        },
    }
    db.commit()

    status = service.latest_scene_status("r1")

    assert status["ndvi_processing"]["status"] == "READY"
    assert status["ndvi_processing"]["mean"] == 0.52
    assert status["ndvi_processing"]["nbr_mean"] == 0.31
    assert "NDVI/NBR processing is ready" in status["message"]


def test_sentinel_acquisition_keeps_unavailable_when_no_scene(tmp_path):
    db = _session()
    provider = _provider_with_transport(lambda request: httpx.Response(200, json={"value": []}, request=request), tmp_path)
    service = SentinelAcquisitionService(db, provider=provider, settings=provider.settings)

    result = service.acquire_latest_scene(["r1"])

    assert result.status == DataQualityStatus.UNAVAILABLE
    assert result.unavailable == 1
    assert result.results[0].status == SentinelAcquisitionStatus.UNAVAILABLE
