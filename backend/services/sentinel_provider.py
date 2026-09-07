from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from backend.core.config import Settings, get_settings
from backend.services.environmental_foundation import (
    DataQualityStatus,
    ProviderErrorKind,
    ProviderName,
    ProviderRequestMetadata,
    ProviderType,
    classify_provider_error,
    classify_freshness,
    provider_operation_completed,
    provider_operation_started,
)
from backend.services.region_registry import RegionLocation, get_region_location

SENTINEL_SOURCE_TYPE = "copernicus_odata_products"
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class SentinelAcquisitionStatus:
    DISCOVERED = "DISCOVERED"
    SELECTED = "SELECTED"
    DOWNLOADING = "DOWNLOADING"
    ACQUIRED = "ACQUIRED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class SentinelProviderError:
    kind: ProviderErrorKind
    message: str
    status_code: int | None = None


@dataclass(frozen=True)
class CopernicusToken:
    access_token: str
    expires_at: datetime

    def usable(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.expires_at - current > timedelta(seconds=60)


@dataclass(frozen=True)
class SentinelSceneCandidate:
    region_id: str
    database_region_id: int
    product_id: str
    name: str
    captured_at: datetime
    retrieved_at: datetime
    cloud_percentage: float
    platform: str | None
    product_level: str
    product_type: str
    content_length: int | None = None
    online: bool = True
    tile_id: str | None = None
    s3_path: str | None = None
    source_url: str | None = None
    footprint: dict[str, Any] | None = None
    checksum: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def quality_status(self) -> DataQualityStatus:
        return classify_freshness(self.captured_at, self.retrieved_at, timedelta(days=14), timedelta(days=5))

    def provenance_metadata(self) -> dict[str, Any]:
        return {
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": SENTINEL_SOURCE_TYPE,
            "product_id": self.product_id,
            "product_name": self.name,
            "platform": self.platform,
            "product_level": self.product_level,
            "product_type": self.product_type,
            "cloud_percentage": self.cloud_percentage,
            "tile_id": self.tile_id,
            "s3_path": self.s3_path,
            "source_url": self.source_url,
            "footprint": self.footprint,
            "checksum": self.checksum,
            "online": self.online,
            "attributes": self.attributes,
        }


@dataclass(frozen=True)
class SentinelProviderResult:
    status: DataQualityStatus
    provider: str
    region_id: str
    retrieved_at: datetime
    scenes: list[SentinelSceneCandidate] = field(default_factory=list)
    selected_scene: SentinelSceneCandidate | None = None
    source_url: str | None = None
    error: SentinelProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status != DataQualityStatus.UNAVAILABLE


@dataclass(frozen=True)
class SentinelDownloadResult:
    status: str
    storage_reference: str | None
    checksum: str | None
    file_size_bytes: int | None
    retrieved_at: datetime
    error: SentinelProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status in {SentinelAcquisitionStatus.ACQUIRED, SentinelAcquisitionStatus.VERIFIED}


class SentinelProvider:
    provider = ProviderName.SENTINEL_2.value
    provider_type = ProviderType.SATELLITE

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self.client = client
        self._token: CopernicusToken | None = None

    def search_scenes(self, region_id: str) -> SentinelProviderResult:
        region = get_region_location(region_id)
        retrieved_at = datetime.now(timezone.utc)
        request = {
            "product_type": self.settings.sentinel_product_type,
            "lookback_days": self.settings.sentinel_lookback_days,
            "max_cloud_cover": self.settings.sentinel_max_cloud_cover,
            "bbox": region.bounding_box(),
        }
        metadata = ProviderRequestMetadata(
            provider=self.provider,
            provider_type=self.provider_type,
            operation="search_scenes",
            region_id=region.id,
            request=request,
        )
        started = provider_operation_started(metadata)

        config_error = self._configuration_error()
        if config_error:
            provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=config_error.kind)
            return SentinelProviderResult(
                status=DataQualityStatus.UNAVAILABLE,
                provider=self.provider,
                region_id=region.id,
                retrieved_at=retrieved_at,
                error=config_error,
            )

        catalog_url = self._catalog_products_url()
        params = self._search_params(region, retrieved_at)
        try:
            response = self._request_with_retries("GET", catalog_url, params=params)
            if response.status_code >= 400:
                error_kind = classify_provider_error(status_code=response.status_code)
                provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=error_kind)
                return SentinelProviderResult(
                    status=DataQualityStatus.UNAVAILABLE,
                    provider=self.provider,
                    region_id=region.id,
                    retrieved_at=retrieved_at,
                    source_url=str(response.request.url),
                    error=SentinelProviderError(error_kind, f"Copernicus catalogue returned HTTP {response.status_code}.", response.status_code),
                )
            payload = response.json()
            scenes = self._parse_search_payload(payload, region, retrieved_at, str(response.request.url))
            selected = self.select_scene(scenes)
            status = selected.quality_status if selected else DataQualityStatus.UNAVAILABLE
            provider_operation_completed(metadata, started, status, record_count=len(scenes))
            return SentinelProviderResult(
                status=status,
                provider=self.provider,
                region_id=region.id,
                retrieved_at=retrieved_at,
                scenes=scenes,
                selected_scene=selected,
                source_url=str(response.request.url),
            )
        except Exception as exc:
            error_kind = classify_provider_error(exc)
            provider_operation_completed(metadata, started, DataQualityStatus.UNAVAILABLE, error_kind=error_kind)
            return SentinelProviderResult(
                status=DataQualityStatus.UNAVAILABLE,
                provider=self.provider,
                region_id=region.id,
                retrieved_at=retrieved_at,
                source_url=catalog_url,
                error=SentinelProviderError(error_kind, str(exc)),
            )

    def select_scene(self, scenes: list[SentinelSceneCandidate]) -> SentinelSceneCandidate | None:
        if not scenes:
            return None
        return sorted(scenes, key=lambda scene: (not scene.online, scene.cloud_percentage, -scene.captured_at.timestamp(), scene.name))[0]

    def download_scene(self, scene: SentinelSceneCandidate, destination_root: str | Path | None = None) -> SentinelDownloadResult:
        retrieved_at = datetime.now(timezone.utc)
        config_error = self._configuration_error(require_credentials=True)
        if config_error:
            return SentinelDownloadResult(SentinelAcquisitionStatus.UNAVAILABLE, None, None, None, retrieved_at, config_error)

        max_bytes = int(self.settings.sentinel_max_scene_size_mb * 1024 * 1024)
        if scene.content_length is not None and scene.content_length > max_bytes:
            return SentinelDownloadResult(
                SentinelAcquisitionStatus.FAILED,
                None,
                None,
                scene.content_length,
                retrieved_at,
                SentinelProviderError(ProviderErrorKind.VALIDATION_ERROR, "Sentinel scene exceeds SENTINEL_MAX_SCENE_SIZE_MB."),
            )

        token = self._access_token()
        safe_name = self._safe_scene_name(scene.product_id or scene.name)
        root = Path(destination_root or self.settings.sentinel_temp_dir)
        final_dir = root / scene.region_id
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / f"{safe_name}.zip"
        part_path = final_dir / f"{safe_name}.{os.getpid()}.part"
        url = f"{self.settings.sentinel_download_url.rstrip('/')}/Products({scene.product_id})/$value"

        hasher = hashlib.sha256()
        bytes_written = 0
        try:
            own_client = self.client is None
            client = self.client or httpx.Client(timeout=self.settings.sentinel_request_timeout)
            try:
                attempts = max(1, self.settings.sentinel_retry_attempts + 1)
                for attempt in range(attempts):
                    self._cleanup_file(part_path)
                    hasher = hashlib.sha256()
                    bytes_written = 0
                    try:
                        with client.stream("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=self.settings.sentinel_request_timeout) as response:
                            if response.status_code in RETRIABLE_STATUS_CODES and attempt < attempts - 1:
                                continue
                            if response.status_code >= 400:
                                error_kind = classify_provider_error(status_code=response.status_code)
                                return SentinelDownloadResult(
                                    SentinelAcquisitionStatus.FAILED,
                                    None,
                                    None,
                                    None,
                                    retrieved_at,
                                    SentinelProviderError(error_kind, f"Copernicus download returned HTTP {response.status_code}.", response.status_code),
                                )
                            content_type = response.headers.get("content-type", "")
                            if "text/html" in content_type.lower():
                                return SentinelDownloadResult(
                                    SentinelAcquisitionStatus.FAILED,
                                    None,
                                    None,
                                    None,
                                    retrieved_at,
                                    SentinelProviderError(ProviderErrorKind.INVALID_RESPONSE, "Copernicus download returned HTML instead of a product archive."),
                                )
                            with part_path.open("wb") as handle:
                                for chunk in response.iter_bytes():
                                    if not chunk:
                                        continue
                                    bytes_written += len(chunk)
                                    if bytes_written > max_bytes:
                                        self._cleanup_file(part_path)
                                        return SentinelDownloadResult(
                                            SentinelAcquisitionStatus.FAILED,
                                            None,
                                            None,
                                            bytes_written,
                                            retrieved_at,
                                            SentinelProviderError(ProviderErrorKind.VALIDATION_ERROR, "Sentinel download exceeded SENTINEL_MAX_SCENE_SIZE_MB."),
                                        )
                                    hasher.update(chunk)
                                    handle.write(chunk)
                            break
                    except (httpx.TimeoutException, httpx.RequestError):
                        if attempt >= attempts - 1:
                            raise
                        time.sleep(self.settings.sentinel_retry_backoff_seconds * (2**attempt))
            finally:
                if own_client:
                    client.close()

            if bytes_written <= 0:
                self._cleanup_file(part_path)
                return SentinelDownloadResult(
                    SentinelAcquisitionStatus.FAILED,
                    None,
                    None,
                    bytes_written,
                    retrieved_at,
                    SentinelProviderError(ProviderErrorKind.INVALID_RESPONSE, "Copernicus download produced an empty file."),
                )
            part_path.replace(final_path)
            return SentinelDownloadResult(SentinelAcquisitionStatus.VERIFIED, str(final_path), hasher.hexdigest(), bytes_written, retrieved_at)
        except Exception as exc:
            self._cleanup_file(part_path)
            return SentinelDownloadResult(
                SentinelAcquisitionStatus.FAILED,
                None,
                None,
                bytes_written or None,
                retrieved_at,
                SentinelProviderError(classify_provider_error(exc), str(exc)),
            )

    def _access_token(self) -> str:
        if self._token and self._token.usable():
            return self._token.access_token
        error = self._configuration_error(require_credentials=True)
        if error:
            raise RuntimeError(error.message)
        response = self._request_with_retries(
            "POST",
            self.settings.copernicus_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.copernicus_client_id or "",
                "client_secret": self.settings.copernicus_client_secret or "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Copernicus authentication returned HTTP {response.status_code}.")
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Copernicus token response did not include access_token.")
        expires_in = int(payload.get("expires_in") or 300)
        self._token = CopernicusToken(access_token=access_token, expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in))
        return access_token

    def _configuration_error(self, require_credentials: bool = True) -> SentinelProviderError | None:
        if not self.settings.sentinel_enabled:
            return SentinelProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "Sentinel acquisition is disabled by SENTINEL_ENABLED.")
        if require_credentials and (not self.settings.copernicus_client_id or not self.settings.copernicus_client_secret):
            return SentinelProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "SENTINEL_ENABLED is true but Copernicus client credentials are not configured.")
        if self.settings.sentinel_lookback_days <= 0:
            return SentinelProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "SENTINEL_LOOKBACK_DAYS must be greater than zero.")
        if not 0 <= self.settings.sentinel_max_cloud_cover <= 100:
            return SentinelProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "SENTINEL_MAX_CLOUD_COVER must be between 0 and 100.")
        if self.settings.sentinel_max_scene_size_mb <= 0:
            return SentinelProviderError(ProviderErrorKind.CONFIGURATION_ERROR, "SENTINEL_MAX_SCENE_SIZE_MB must be greater than zero.")
        return None

    def _request_with_retries(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempts = max(1, self.settings.sentinel_retry_attempts + 1)
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=self.settings.sentinel_request_timeout)
        last_response: httpx.Response | None = None
        last_error: Exception | None = None
        try:
            for attempt in range(attempts):
                try:
                    response = client.request(method, url, timeout=self.settings.sentinel_request_timeout, **kwargs)
                    last_response = response
                    if response.status_code not in RETRIABLE_STATUS_CODES:
                        return response
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self.settings.sentinel_retry_backoff_seconds * (2**attempt))
            if last_response is not None:
                return last_response
            if last_error is not None:
                raise last_error
            raise RuntimeError("Copernicus request failed without response.")
        finally:
            if own_client:
                client.close()

    def _catalog_products_url(self) -> str:
        return f"{(self.settings.sentinel_catalog_url or self.settings.sentinel_base_url).rstrip('/')}/Products"

    def _search_params(self, region: RegionLocation, retrieved_at: datetime) -> dict[str, str | int]:
        start = (retrieved_at - timedelta(days=self.settings.sentinel_lookback_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        end = retrieved_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        west, south, east, north = region.bounding_box()
        polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        product_type = self.settings.sentinel_product_type.strip()
        filters = [
            "Collection/Name eq 'SENTINEL-2'",
            f"ContentDate/Start ge {start}",
            f"ContentDate/Start le {end}",
            (
                "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
                f"and att/OData.CSC.DoubleAttribute/Value le {self.settings.sentinel_max_cloud_cover:.2f})"
            ),
            (
                "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
                f"and att/OData.CSC.StringAttribute/Value eq '{product_type}')"
            ),
            f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')",
        ]
        return {
            "$filter": " and ".join(filters),
            "$orderby": "ContentDate/Start desc",
            "$top": 20,
            "$expand": "Attributes",
        }

    def _parse_search_payload(self, payload: dict[str, Any], region: RegionLocation, retrieved_at: datetime, source_url: str) -> list[SentinelSceneCandidate]:
        values = payload.get("value")
        if not isinstance(values, list):
            raise ValueError("Copernicus catalogue response missing value array.")
        scenes: list[SentinelSceneCandidate] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            scene = self._candidate_from_item(item, region, retrieved_at, source_url)
            if scene:
                scenes.append(scene)
        return scenes

    def _candidate_from_item(self, item: dict[str, Any], region: RegionLocation, retrieved_at: datetime, source_url: str) -> SentinelSceneCandidate | None:
        product_id = str(item.get("Id") or "").strip()
        name = str(item.get("Name") or "").strip()
        content_date = item.get("ContentDate") if isinstance(item.get("ContentDate"), dict) else {}
        captured_at = self._parse_datetime(content_date.get("Start") or item.get("OriginDate") or item.get("PublicationDate"))
        if not product_id or not name or not captured_at:
            return None
        attributes = self._attributes_dict(item.get("Attributes"))
        cloud = self._float(attributes.get("cloudCover") or item.get("CloudCover") or 100.0)
        product_type = str(attributes.get("productType") or self.settings.sentinel_product_type)
        product_level = self._product_level(name, product_type)
        platform = self._platform(name)
        return SentinelSceneCandidate(
            region_id=region.id,
            database_region_id=region.database_id,
            product_id=product_id,
            name=name,
            captured_at=captured_at,
            retrieved_at=retrieved_at,
            cloud_percentage=cloud,
            platform=platform,
            product_level=product_level,
            product_type=product_type,
            content_length=self._optional_int(item.get("ContentLength")),
            online=bool(item.get("Online", True)),
            tile_id=str(attributes.get("tileIdentifier") or self._tile_id(name) or "") or None,
            s3_path=item.get("S3Path"),
            source_url=source_url,
            footprint=item.get("GeoFootprint") or item.get("Geofootprint") or item.get("Footprint"),
            checksum=self._checksum(item.get("Checksum")),
            attributes=attributes,
            raw_metadata={key: item.get(key) for key in ("Id", "Name", "ContentDate", "PublicationDate", "OriginDate", "Online", "ContentLength", "S3Path")},
        )

    def _attributes_dict(self, attributes: Any) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        if not isinstance(attributes, list):
            return normalized
        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue
            name = attribute.get("Name")
            if not isinstance(name, str):
                continue
            normalized[name] = attribute.get("Value")
        return normalized

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _platform(self, name: str) -> str | None:
        match = re.match(r"^(S2[A-Z])_", name)
        return match.group(1) if match else None

    def _product_level(self, name: str, product_type: str) -> str:
        if "MSIL2A" in name or product_type == "S2MSI2A":
            return "L2A"
        if "MSIL1C" in name or product_type == "S2MSI1C":
            return "L1C"
        return product_type

    def _tile_id(self, name: str) -> str | None:
        match = re.search(r"_T([A-Z0-9]{5})_", name)
        return match.group(1) if match else None

    def _checksum(self, checksum: Any) -> str | None:
        if isinstance(checksum, list) and checksum:
            first = checksum[0]
            if isinstance(first, dict):
                return str(first.get("Value") or "") or None
        if isinstance(checksum, dict):
            return str(checksum.get("Value") or "") or None
        if isinstance(checksum, str):
            return checksum
        return None

    def _float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 100.0

    def _optional_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_scene_name(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:180] or "sentinel_scene"

    def _cleanup_file(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
