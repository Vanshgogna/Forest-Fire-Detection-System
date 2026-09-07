from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.database.models import SatelliteImage
from backend.repositories.environment import RegionRepository, SatelliteImageRepository
from backend.services.environmental_foundation import DataQualityStatus, FreshnessPolicy, ProviderName
from backend.services.region_registry import get_region_location, list_region_locations
from backend.services.sentinel_provider import (
    SENTINEL_SOURCE_TYPE,
    SentinelAcquisitionStatus,
    SentinelDownloadResult,
    SentinelProvider,
    SentinelProviderError,
    SentinelSceneCandidate,
)


@dataclass(frozen=True)
class SentinelRegionAcquisition:
    region_id: str
    status: str
    quality_status: DataQualityStatus
    product_id: str | None = None
    scene_id: str | None = None
    already_present: bool = False
    storage_reference: str | None = None
    checksum: str | None = None
    file_size_bytes: int | None = None
    cloud_percentage: float | None = None
    captured_at: datetime | None = None
    retrieved_at: datetime | None = None
    error: SentinelProviderError | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "status": self.status,
            "quality_status": self.quality_status.value,
            "product_id": self.product_id,
            "scene_id": self.scene_id,
            "already_present": self.already_present,
            "storage_available": bool(self.storage_reference),
            "storage_reference": self.storage_reference,
            "checksum": self.checksum,
            "file_size_bytes": self.file_size_bytes,
            "cloud_percentage": self.cloud_percentage,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "error": {
                "kind": self.error.kind.value,
                "message": self.error.message,
                "status_code": self.error.status_code,
            }
            if self.error
            else None,
        }


@dataclass(frozen=True)
class SentinelAcquisitionSummary:
    status: DataQualityStatus
    provider: str
    requested_regions: list[str]
    acquired: int = 0
    reused: int = 0
    failed: int = 0
    unavailable: int = 0
    results: list[SentinelRegionAcquisition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "provider": self.provider,
            "requested_regions": self.requested_regions,
            "acquired": self.acquired,
            "reused": self.reused,
            "failed": self.failed,
            "unavailable": self.unavailable,
            "results": [result.to_dict() for result in self.results],
        }


class SentinelAcquisitionService:
    def __init__(self, db: Session, provider: SentinelProvider | None = None, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.provider = provider or SentinelProvider(settings=self.settings)
        self.regions = RegionRepository(db)
        self.scenes = SatelliteImageRepository(db)

    def acquire_latest_scene(self, region_ids: list[str] | None = None, download: bool = True) -> SentinelAcquisitionSummary:
        requested = region_ids or [region.id for region in list_region_locations()]
        results = [self._acquire_region(region_id, download=download) for region_id in requested]
        acquired = sum(1 for result in results if result.status == SentinelAcquisitionStatus.VERIFIED and not result.already_present)
        reused = sum(1 for result in results if result.already_present)
        failed = sum(1 for result in results if result.status == SentinelAcquisitionStatus.FAILED)
        unavailable = sum(1 for result in results if result.status == SentinelAcquisitionStatus.UNAVAILABLE)
        status = self._summary_status(results)
        self.db.commit()
        return SentinelAcquisitionSummary(
            status=status,
            provider=ProviderName.SENTINEL_2.value,
            requested_regions=requested,
            acquired=acquired,
            reused=reused,
            failed=failed,
            unavailable=unavailable,
            results=results,
        )

    def latest_scene_status(self, region_id: str) -> dict[str, Any]:
        region = get_region_location(region_id)
        record = self.scenes.latest_sentinel_for_region(region.database_id)
        if not record:
            return self._unavailable_status(region.id, "No Sentinel-2 scene has been acquired for this region.")
        return self.scene_status_payload(record, region.id)

    def scene_status_payload(self, record: SatelliteImage, region_id: str | None = None) -> dict[str, Any]:
        metadata = record.metadata_json or {}
        raster = metadata.get("raster_processing") or {}
        quality = metadata.get("quality_masking") or {}
        quality_stats = quality.get("stats") or {}
        ndvi = metadata.get("ndvi_processing") or {}
        ndvi_stats = ndvi.get("statistics") or {}
        return {
            "region_id": region_id,
            "available": record.acquisition_status in {SentinelAcquisitionStatus.ACQUIRED, SentinelAcquisitionStatus.VERIFIED},
            "provider": record.provider,
            "source_type": metadata.get("source_type", SENTINEL_SOURCE_TYPE),
            "status": record.quality_status,
            "acquisition_status": record.acquisition_status,
            "product_id": record.product_id,
            "scene_id": record.scene_id,
            "platform": record.platform,
            "product_level": record.product_level,
            "captured_at": record.captured_at.isoformat() if record.captured_at else None,
            "retrieved_at": record.retrieved_at.isoformat() if record.retrieved_at else None,
            "cloud_percentage": record.cloud_percentage,
            "tile_id": record.tile_id,
            "storage_available": bool(record.storage_reference),
            "file_size_bytes": record.file_size_bytes,
            "checksum": record.checksum,
            "raster_processing": {
                "status": raster.get("status", "DISCOVERED"),
                "available_bands": raster.get("available_bands", []),
                "analysis_crs": raster.get("analysis_crs"),
                "resolution": raster.get("resolution"),
                "processing_time": record.processing_time.isoformat() if record.processing_time else None,
            },
            "quality_masking": {
                "status": quality.get("status", "DISCOVERED"),
                "quality_status": quality.get("quality_status"),
                "masking_version": quality.get("masking_version"),
                "valid_pixel_percentage": quality_stats.get("valid_pixel_percentage"),
                "masked_pixel_percentage": quality_stats.get("masked_pixel_percentage"),
                "cloud_percentage": quality_stats.get("cloud_percentage"),
                "shadow_percentage": quality_stats.get("shadow_percentage"),
                "cirrus_percentage": quality_stats.get("cirrus_percentage"),
                "snow_percentage": quality_stats.get("snow_percentage"),
                "processed_at": quality.get("completed_at"),
            },
            "ndvi_processing": {
                "status": ndvi.get("status", "DISCOVERED"),
                "quality_status": ndvi.get("quality_status"),
                "processing_version": ndvi.get("processing_version"),
                "mean": ndvi_stats.get("mean"),
                "median": ndvi_stats.get("median"),
                "min": ndvi_stats.get("min"),
                "max": ndvi_stats.get("max"),
                "valid_pixel_percentage": ndvi_stats.get("valid_pixel_percentage"),
                "processed_at": ndvi.get("processed_at"),
            },
            "message": "Sentinel-2 scene acquired; NBR and fire-risk processing are not implemented in this phase.",
            "attribution": "Copernicus Data Space Ecosystem",
        }

    def _acquire_region(self, region_id: str, download: bool) -> SentinelRegionAcquisition:
        region = get_region_location(region_id)
        self.regions.get_or_create_from_registry(region)
        search = self.provider.search_scenes(region.id)
        if not search.selected_scene:
            return SentinelRegionAcquisition(
                region_id=region.id,
                status=SentinelAcquisitionStatus.UNAVAILABLE,
                quality_status=DataQualityStatus.UNAVAILABLE,
                error=search.error,
            )

        scene = search.selected_scene
        existing = self.scenes.by_product_id(ProviderName.SENTINEL_2.value, scene.product_id)
        if existing and existing.acquisition_status in {SentinelAcquisitionStatus.ACQUIRED, SentinelAcquisitionStatus.VERIFIED} and existing.storage_reference:
            return self._result_from_record(region.id, existing, already_present=True)

        record = existing or self._new_record(scene)
        self._apply_scene_metadata(record, scene, SentinelAcquisitionStatus.SELECTED)
        self.db.flush()

        if not download:
            return self._result_from_record(region.id, record, already_present=bool(existing))

        record.acquisition_status = SentinelAcquisitionStatus.DOWNLOADING
        self.db.flush()
        download_result = self.provider.download_scene(scene)
        self._apply_download_result(record, download_result, scene)
        self.db.flush()
        return self._result_from_record(region.id, record, already_present=False, error=download_result.error)

    def _new_record(self, scene: SentinelSceneCandidate) -> SatelliteImage:
        record = SatelliteImage(
            region_id=scene.database_region_id,
            source="Sentinel-2",
            scene_id=scene.name,
            provider=ProviderName.SENTINEL_2.value,
            product_id=scene.product_id,
            captured_at=scene.captured_at.replace(tzinfo=None),
            cloud_percentage=scene.cloud_percentage,
            metadata_json={},
        )
        self.db.add(record)
        return record

    def _apply_scene_metadata(self, record: SatelliteImage, scene: SentinelSceneCandidate, status: str) -> None:
        record.region_id = scene.database_region_id
        record.source = "Sentinel-2"
        record.scene_id = scene.name
        record.provider = ProviderName.SENTINEL_2.value
        record.product_id = scene.product_id
        record.platform = scene.platform
        record.product_level = scene.product_level
        record.captured_at = scene.captured_at.replace(tzinfo=None)
        record.retrieved_at = scene.retrieved_at.replace(tzinfo=None)
        record.cloud_percentage = scene.cloud_percentage
        record.tile_id = scene.tile_id
        record.source_reference = scene.source_url
        record.file_size_bytes = scene.content_length
        record.checksum = scene.checksum
        record.quality_status = scene.quality_status.value
        record.acquisition_status = status
        record.metadata_json = {"source_type": SENTINEL_SOURCE_TYPE, **scene.provenance_metadata()}

    def _apply_download_result(self, record: SatelliteImage, result: SentinelDownloadResult, scene: SentinelSceneCandidate) -> None:
        record.retrieved_at = result.retrieved_at.replace(tzinfo=None)
        if result.ok:
            record.storage_reference = result.storage_reference
            record.file_url = result.storage_reference
            record.file_size_bytes = result.file_size_bytes
            record.checksum = result.checksum
            record.acquisition_status = SentinelAcquisitionStatus.VERIFIED
            record.quality_status = self._quality_for_scene(scene, result.retrieved_at).value
            record.metadata_json = {
                **(record.metadata_json or {}),
                "downloaded_at": result.retrieved_at.isoformat(),
                "storage_reference_type": "local_file",
            }
        else:
            record.acquisition_status = SentinelAcquisitionStatus.FAILED
            record.quality_status = DataQualityStatus.UNAVAILABLE.value
            record.metadata_json = {
                **(record.metadata_json or {}),
                "download_error": {
                    "kind": result.error.kind.value if result.error else None,
                    "message": result.error.message if result.error else "Unknown Sentinel download error.",
                    "status_code": result.error.status_code if result.error else None,
                },
            }

    def _quality_for_scene(self, scene: SentinelSceneCandidate, retrieved_at: datetime) -> DataQualityStatus:
        max_age = FreshnessPolicy.from_settings(self.settings).vegetation_max_age
        return scene.quality_status if scene.quality_status == DataQualityStatus.SUSPICIOUS else self._freshness(scene.captured_at, retrieved_at, max_age)

    def _freshness(self, captured_at: datetime, retrieved_at: datetime, max_age) -> DataQualityStatus:
        from backend.services.environmental_foundation import classify_freshness

        return classify_freshness(captured_at, retrieved_at, max_age, max_age / 2)

    def _result_from_record(
        self,
        region_id: str,
        record: SatelliteImage,
        already_present: bool,
        error: SentinelProviderError | None = None,
    ) -> SentinelRegionAcquisition:
        captured_at = self._aware(record.captured_at)
        retrieved_at = self._aware(record.retrieved_at)
        return SentinelRegionAcquisition(
            region_id=region_id,
            status=record.acquisition_status,
            quality_status=DataQualityStatus(record.quality_status),
            product_id=record.product_id,
            scene_id=record.scene_id,
            already_present=already_present,
            storage_reference=record.storage_reference,
            checksum=record.checksum,
            file_size_bytes=record.file_size_bytes,
            cloud_percentage=record.cloud_percentage,
            captured_at=captured_at,
            retrieved_at=retrieved_at,
            error=error,
        )

    def _summary_status(self, results: list[SentinelRegionAcquisition]) -> DataQualityStatus:
        if any(result.quality_status == DataQualityStatus.LIVE for result in results):
            return DataQualityStatus.LIVE
        if any(result.quality_status == DataQualityStatus.RECENT for result in results):
            return DataQualityStatus.RECENT
        if any(result.quality_status == DataQualityStatus.STALE for result in results):
            return DataQualityStatus.STALE
        return DataQualityStatus.UNAVAILABLE

    def _unavailable_status(self, region_id: str, message: str) -> dict[str, Any]:
        return {
            "region_id": region_id,
            "available": False,
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": SENTINEL_SOURCE_TYPE,
            "status": DataQualityStatus.UNAVAILABLE.value,
            "acquisition_status": SentinelAcquisitionStatus.UNAVAILABLE,
            "product_id": None,
            "scene_id": None,
            "platform": None,
            "product_level": self.settings.sentinel_product_type,
            "captured_at": None,
            "retrieved_at": None,
            "cloud_percentage": None,
            "tile_id": None,
            "storage_available": False,
            "file_size_bytes": None,
            "checksum": None,
            "message": message,
            "attribution": "Copernicus Data Space Ecosystem",
        }

    def _aware(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
