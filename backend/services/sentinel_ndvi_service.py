from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.database.models import SatelliteImage, VegetationRecord
from backend.repositories.environment import RegionRepository, SatelliteImageRepository
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind, ProviderName, classify_provider_error
from backend.services.region_registry import get_region_location
from backend.services.sentinel_provider import SENTINEL_SOURCE_TYPE, SentinelAcquisitionStatus, SentinelProvider, SentinelSceneCandidate
from backend.services.sentinel_quality_mask_service import SentinelQualityMaskStatus
from backend.services.sentinel_raster_service import PROCESSING_OUTPUT_NODATA, SentinelRasterService, SentinelRasterStatus

NDVI_SOURCE_TYPE = "sentinel2_l2a_ndvi_processing"
NDVI_OUTPUT_NODATA = PROCESSING_OUTPUT_NODATA
NDVI_RANGE_TOLERANCE = 1e-5
NDVI_REQUIRED_BANDS = {"RED": "B04", "NIR": "B08"}
NBR_REQUIRED_BANDS = {"NIR": "B08", "SWIR2": "B12"}
SENTINEL_HUB_PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"
PROCESS_API_OUTPUT_SIZE = 256
PROCESS_API_VALID_SCL_CLASSES = {4, 5}


class SentinelNDVIStatus:
    DISCOVERED = "DISCOVERED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    LOW_QUALITY = "LOW_QUALITY"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class NDVIError:
    kind: ProviderErrorKind
    message: str


@dataclass(frozen=True)
class NDVIStats:
    total_pixels: int
    valid_pixels: int
    invalid_pixels: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    standard_deviation: float | None
    percentiles: dict[str, float | None] = field(default_factory=dict)

    @property
    def valid_pixel_percentage(self) -> float:
        if self.total_pixels <= 0:
            return 0.0
        return round((self.valid_pixels / self.total_pixels) * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_pixels": self.total_pixels,
            "valid_pixels": self.valid_pixels,
            "invalid_pixels": self.invalid_pixels,
            "valid_pixel_percentage": self.valid_pixel_percentage,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "median": self.median,
            "standard_deviation": self.standard_deviation,
            "p10": self.percentiles.get("p10"),
            "p25": self.percentiles.get("p25"),
            "p50": self.percentiles.get("p50"),
            "p75": self.percentiles.get("p75"),
            "p90": self.percentiles.get("p90"),
        }


@dataclass(frozen=True)
class NDVISummary:
    region_id: str
    scene_id: str
    product_id: str
    acquisition_time: datetime
    processed_at: datetime
    status: str
    quality_status: DataQualityStatus
    processing_version: str
    analysis_crs: str
    resolution: tuple[float, float]
    width: int
    height: int
    transform: tuple[float, float, float, float, float, float]
    ndvi_reference: str
    ndvi_valid_mask_reference: str
    stats: NDVIStats
    vegetation_record_id: int | None
    provenance: dict[str, Any]
    nbr_reference: str | None = None
    nbr_valid_mask_reference: str | None = None
    nbr_stats: NDVIStats | None = None

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "scene_id": self.scene_id,
            "product_id": self.product_id,
            "acquisition_time": self.acquisition_time.isoformat(),
            "processed_at": self.processed_at.isoformat(),
            "status": self.status,
            "quality_status": self.quality_status.value,
            "processing_version": self.processing_version,
            "analysis_crs": self.analysis_crs,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "transform": self.transform,
            "ndvi": self.ndvi_reference if expose_paths else Path(self.ndvi_reference).name,
            "ndvi_valid_mask": self.ndvi_valid_mask_reference if expose_paths else Path(self.ndvi_valid_mask_reference).name,
            "nbr": self.nbr_reference if expose_paths and self.nbr_reference else Path(self.nbr_reference).name if self.nbr_reference else None,
            "nbr_valid_mask": self.nbr_valid_mask_reference if expose_paths and self.nbr_valid_mask_reference else Path(self.nbr_valid_mask_reference).name if self.nbr_valid_mask_reference else None,
            "statistics": self.stats.to_dict(),
            "nbr_statistics": self.nbr_stats.to_dict() if self.nbr_stats else None,
            "vegetation_record_id": self.vegetation_record_id,
            "provenance": self.provenance if expose_paths else self._redacted_provenance(),
        }

    def _redacted_provenance(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.provenance.items()
            if key not in {"analysis_manifest_path", "quality_manifest_path", "ndvi_path", "ndvi_valid_mask_path", "nbr_path", "nbr_valid_mask_path", "input_paths", "manifest_path"}
        }


@dataclass(frozen=True)
class NDVIResult:
    status: str
    quality_status: DataQualityStatus
    summary: NDVISummary | None = None
    error: NDVIError | None = None

    @property
    def ok(self) -> bool:
        return self.status in {SentinelNDVIStatus.READY, SentinelNDVIStatus.LOW_QUALITY} and self.summary is not None

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "quality_status": self.quality_status.value,
            "summary": self.summary.to_dict(expose_paths=expose_paths) if self.summary else None,
            "error": {"kind": self.error.kind.value, "message": self.error.message} if self.error else None,
        }


class SentinelNDVIService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.rasters = SentinelRasterService(db, settings=self.settings)
        self.scenes = SatelliteImageRepository(db)

    def calculate_ndvi(self, region_id: str, scene_id: str | None = None) -> NDVIResult:
        started_at = datetime.now(timezone.utc)
        scene: SatelliteImage | None = None
        try:
            region = get_region_location(region_id)
            scene = self.rasters._locate_scene(region.database_id, scene_id)
            if not scene:
                if self._can_use_process_api(scene_id):
                    return self._calculate_from_process_api(region.id, started_at)
                return self._failure(SentinelNDVIStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.", ProviderErrorKind.CONFIGURATION_ERROR)
            cached = self._cached_result(scene, region.id)
            if cached:
                return NDVIResult(cached.status, cached.quality_status, cached)
            prerequisite_error = self._prerequisite_error(scene)
            if prerequisite_error:
                if self._can_use_process_api(scene_id):
                    return self._calculate_from_process_api(region.id, started_at, scene=scene)
                return self._failure(SentinelNDVIStatus.UNAVAILABLE, prerequisite_error, ProviderErrorKind.CONFIGURATION_ERROR)
            metadata = scene.metadata_json or {}
            raster_metadata = metadata["raster_processing"]
            quality_metadata = metadata["quality_masking"]
            analysis_manifest_path = Path(raster_metadata["manifest_path"])
            quality_manifest_path = Path(quality_metadata["manifest_path"])
            analysis_manifest = self._read_manifest(analysis_manifest_path, "analysis-ready")
            quality_manifest = self._read_manifest(quality_manifest_path, "quality")
            self._set_processing_state(scene, SentinelNDVIStatus.PROCESSING, started_at=started_at)
            summary = self._process(scene, region.id, analysis_manifest_path, quality_manifest_path, analysis_manifest, quality_manifest, started_at)
            record = self._upsert_vegetation_record(scene, region.database_id, summary)
            summary = self._with_record_id(summary, record.id)
            self._rewrite_manifest(summary)
            self._set_processing_state(scene, summary.status, started_at=started_at, summary=summary)
            self.db.commit()
            return NDVIResult(summary.status, summary.quality_status, summary)
        except Exception as exc:
            self.db.rollback()
            if scene is not None:
                self._set_failure_state(scene, started_at, str(exc))
            return self._failure(SentinelNDVIStatus.FAILED, str(exc), classify_provider_error(exc))

    def _can_use_process_api(self, scene_id: str | None) -> bool:
        return bool(self.settings.sentinel_enabled and self.settings.copernicus_client_id and self.settings.copernicus_client_secret and not scene_id)

    def _calculate_from_process_api(self, region_id: str, started_at: datetime, scene: SatelliteImage | None = None) -> NDVIResult:
        region = get_region_location(region_id)
        provider = SentinelProvider(settings=self.settings)
        selected_scene = None
        if scene is None:
            search = provider.search_scenes(region.id)
            if search.error:
                return self._failure(SentinelNDVIStatus.UNAVAILABLE, search.error.message, search.error.kind)
            if not search.selected_scene:
                return self._failure(SentinelNDVIStatus.UNAVAILABLE, "No Sentinel-2 L2A scene matched the configured region, cloud, and lookback filters.", ProviderErrorKind.INVALID_RESPONSE)
            selected_scene = search.selected_scene
            scene = self._upsert_scene_from_candidate(selected_scene)
        else:
            selected_scene = self._candidate_from_record(scene, region.id)

        cached = self._cached_result(scene, region.id)
        if cached:
            return NDVIResult(cached.status, cached.quality_status, cached)

        self._set_processing_state(scene, SentinelNDVIStatus.PROCESSING, started_at=started_at, message="Sentinel Hub Process API NDVI processing in progress.")
        summary = self._process_api_ndvi(provider, scene, selected_scene, region.id, started_at)
        record = self._upsert_vegetation_record(scene, region.database_id, summary)
        summary = self._with_record_id(summary, record.id)
        self._rewrite_manifest(summary)
        self._set_processing_state(scene, summary.status, started_at=started_at, summary=summary)
        scene.acquisition_status = SentinelAcquisitionStatus.VERIFIED
        scene.quality_status = summary.quality_status.value
        scene.processing_time = summary.processed_at.replace(tzinfo=None)
        self.db.commit()
        return NDVIResult(summary.status, summary.quality_status, summary)

    def _upsert_scene_from_candidate(self, candidate: SentinelSceneCandidate) -> SatelliteImage:
        RegionRepository(self.db).get_or_create_from_registry(get_region_location(candidate.region_id))
        record = self.scenes.by_product_id(ProviderName.SENTINEL_2.value, candidate.product_id)
        if record is None:
            record = SatelliteImage(
                region_id=candidate.database_region_id,
                source="Sentinel-2",
                scene_id=candidate.name,
                provider=ProviderName.SENTINEL_2.value,
                product_id=candidate.product_id,
                captured_at=candidate.captured_at.replace(tzinfo=None),
                metadata_json={},
            )
            self.db.add(record)
        record.region_id = candidate.database_region_id
        record.source = "Sentinel-2"
        record.scene_id = candidate.name
        record.provider = ProviderName.SENTINEL_2.value
        record.product_id = candidate.product_id
        record.platform = candidate.platform
        record.product_level = candidate.product_level
        record.captured_at = candidate.captured_at.replace(tzinfo=None)
        record.retrieved_at = candidate.retrieved_at.replace(tzinfo=None)
        record.cloud_percentage = candidate.cloud_percentage
        record.tile_id = candidate.tile_id
        record.source_reference = candidate.source_url
        record.file_size_bytes = candidate.content_length
        record.checksum = candidate.checksum
        record.quality_status = candidate.quality_status.value
        record.acquisition_status = SentinelAcquisitionStatus.SELECTED
        record.metadata_json = {**(record.metadata_json or {}), "source_type": SENTINEL_SOURCE_TYPE, **candidate.provenance_metadata()}
        self.db.flush()
        return record

    def _candidate_from_record(self, scene: SatelliteImage, region_id: str) -> SentinelSceneCandidate:
        region = get_region_location(region_id)
        captured_at = self.rasters._aware(scene.captured_at) or datetime.now(timezone.utc)
        retrieved_at = datetime.now(timezone.utc)
        metadata = scene.metadata_json or {}
        return SentinelSceneCandidate(
            region_id=region.id,
            database_region_id=region.database_id,
            product_id=scene.product_id or scene.scene_id or "unknown",
            name=scene.scene_id or scene.product_id or "unknown",
            captured_at=captured_at,
            retrieved_at=retrieved_at,
            cloud_percentage=float(scene.cloud_percentage or 0),
            platform=scene.platform,
            product_level=scene.product_level or "L2A",
            product_type=str(metadata.get("product_type") or self.settings.sentinel_product_type),
            content_length=scene.file_size_bytes,
            online=True,
            tile_id=scene.tile_id,
            s3_path=metadata.get("s3_path"),
            source_url=scene.source_reference,
            footprint=metadata.get("footprint"),
            checksum=scene.checksum,
            attributes=metadata.get("attributes") or {},
            raw_metadata=metadata.get("raw_metadata") or {},
        )

    def _process_api_ndvi(self, provider: SentinelProvider, scene: SatelliteImage, candidate: SentinelSceneCandidate, region_id: str, started_at: datetime) -> NDVISummary:
        token = provider._access_token()
        payload = self._process_api_payload(candidate)
        response = self._process_api_request(token, payload)
        red, nir, swir2, scl, data_mask, profile = self._read_process_api_tiff(response.content, region_id)
        red, nir, swir2 = self._normalize_process_reflectance(red, nir, swir2)
        pixel_valid = data_mask > 0.5
        quality_valid = np.isin(np.rint(scl).astype("int16"), list(PROCESS_API_VALID_SCL_CLASSES))
        ndvi_data, ndvi_valid = self._calculate_index_window(red, nir, pixel_valid, quality_valid)
        nbr_data, nbr_valid = self._calculate_index_window(swir2, nir, pixel_valid, quality_valid)
        if not ndvi_valid.any():
            raise ValueError("Sentinel Hub Process API NDVI calculation produced no valid pixels.")
        if not nbr_valid.any():
            raise ValueError("Sentinel Hub Process API NBR calculation produced no valid pixels.")

        output_dir = self.rasters._output_dir(scene, region_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        ndvi_path = output_dir / "ndvi.tif"
        ndvi_valid_mask_path = output_dir / "ndvi_valid_mask.tif"
        nbr_path = output_dir / "nbr.tif"
        nbr_valid_mask_path = output_dir / "nbr_valid_mask.tif"
        ndvi_profile = {**profile, "driver": "GTiff", "count": 1, "dtype": "float32", "nodata": NDVI_OUTPUT_NODATA, "compress": "deflate"}
        mask_profile = {**profile, "driver": "GTiff", "count": 1, "dtype": "uint8", "nodata": 0, "compress": "deflate"}
        with rasterio.open(ndvi_path, "w", **ndvi_profile) as destination:
            destination.write(ndvi_data.astype("float32"), 1)
        with rasterio.open(ndvi_valid_mask_path, "w", **mask_profile) as destination:
            destination.write(ndvi_valid.astype("uint8"), 1)
        with rasterio.open(nbr_path, "w", **ndvi_profile) as destination:
            destination.write(nbr_data.astype("float32"), 1)
        with rasterio.open(nbr_valid_mask_path, "w", **mask_profile) as destination:
            destination.write(nbr_valid.astype("uint8"), 1)

        stats = self._stats(int(ndvi_data.size), [ndvi_data[ndvi_valid].astype("float32")])
        nbr_stats = self._stats(int(nbr_data.size), [nbr_data[nbr_valid].astype("float32")])
        status = SentinelNDVIStatus.READY
        quality_status = DataQualityStatus.LIVE
        if min(stats.valid_pixel_percentage, nbr_stats.valid_pixel_percentage) < self.settings.sentinel_min_valid_pixel_percent:
            status = SentinelNDVIStatus.LOW_QUALITY
            quality_status = DataQualityStatus.SUSPICIOUS
        completed_at = datetime.now(timezone.utc)
        provenance = {
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": NDVI_SOURCE_TYPE,
            "processing_version": self.settings.sentinel_ndvi_processing_version,
            "scene_id": scene.scene_id,
            "product_id": scene.product_id,
            "region_id": region_id,
            "source_api": "sentinel_hub_process_api",
            "source_url": SENTINEL_HUB_PROCESS_URL,
            "formula": "(NIR - RED) / (NIR + RED)",
            "nbr_formula": "(B08 - B12) / (B08 + B12)",
            "red_band": "B04",
            "nir_band": "B08",
            "swir2_band": "B12",
            "quality_mask_source": "Sentinel Hub Process API dataMask and Sentinel-2 L2A SCL classes 4/5",
            "input_reflectance": "Sentinel Hub Process API Sentinel-2 L2A B04/B08/B12 reflectance; no full OData product download",
            "cloud_percentage": scene.cloud_percentage,
            "tile_id": scene.tile_id,
            "process_api_output_size": [profile["width"], profile["height"]],
            "ndvi_path": str(ndvi_path),
            "ndvi_valid_mask_path": str(ndvi_valid_mask_path),
            "nbr_path": str(nbr_path),
            "nbr_valid_mask_path": str(nbr_valid_mask_path),
            "nodata": NDVI_OUTPUT_NODATA,
            "zero_denominator": "masked_as_invalid",
            "range_validation": f"valid NDVI must be within [-1, 1] with tolerance {NDVI_RANGE_TOLERANCE}",
            "processing_started_at": started_at.isoformat(),
            "processed_at": completed_at.isoformat(),
            "low_quality_threshold_percent": self.settings.sentinel_min_valid_pixel_percent,
            "statistics": stats.to_dict(),
            "nbr_statistics": nbr_stats.to_dict(),
            "fire_risk_scoring": "not_implemented_in_part_6d_3",
        }
        summary = NDVISummary(
            region_id=region_id,
            scene_id=scene.scene_id or "",
            product_id=scene.product_id or "",
            acquisition_time=self.rasters._aware(scene.captured_at) or candidate.captured_at,
            processed_at=completed_at,
            status=status,
            quality_status=quality_status,
            processing_version=self.settings.sentinel_ndvi_processing_version,
            analysis_crs=str(profile.get("crs") or "EPSG:4326"),
            resolution=(abs(profile["transform"].a), abs(profile["transform"].e)),
            width=int(profile["width"]),
            height=int(profile["height"]),
            transform=(profile["transform"].a, profile["transform"].b, profile["transform"].c, profile["transform"].d, profile["transform"].e, profile["transform"].f),
            ndvi_reference=str(ndvi_path),
            ndvi_valid_mask_reference=str(ndvi_valid_mask_path),
            stats=stats,
            vegetation_record_id=None,
            provenance=provenance,
            nbr_reference=str(nbr_path),
            nbr_valid_mask_reference=str(nbr_valid_mask_path),
            nbr_stats=nbr_stats,
        )
        manifest_path = output_dir / "ndvi_manifest.json"
        manifest_payload = summary.to_dict(expose_paths=True)
        manifest_payload["part"] = "6D-3 SENTINEL-2 NDVI PROCESSING - Sentinel Hub Process API path"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, default=str))
        summary.provenance["manifest_path"] = str(manifest_path)
        return summary

    def _process_api_payload(self, candidate: SentinelSceneCandidate) -> dict[str, Any]:
        west, south, east, north = get_region_location(candidate.region_id).bounding_box()
        captured = candidate.captured_at.astimezone(timezone.utc)
        day_start = captured.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        day_end = captured.replace(hour=23, minute=59, second=59, microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "input": {
                "bounds": {
                    "bbox": [west, south, east, north],
                    "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                },
                "data": [
                    {
                        "type": "S2L2A",
                        "dataFilter": {
                            "timeRange": {"from": day_start, "to": day_end},
                            "maxCloudCoverage": self.settings.sentinel_max_cloud_cover,
                            "mosaickingOrder": "leastCC",
                        },
                    }
                ],
            },
            "output": {
                "width": PROCESS_API_OUTPUT_SIZE,
                "height": PROCESS_API_OUTPUT_SIZE,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": self._process_api_evalscript(),
        }

    def _process_api_request(self, token: str, payload: dict[str, Any]) -> httpx.Response:
        attempts = max(1, self.settings.sentinel_retry_attempts + 1)
        last_response: httpx.Response | None = None
        last_error: Exception | None = None
        with httpx.Client(timeout=self.settings.sentinel_request_timeout) as client:
            for attempt in range(attempts):
                try:
                    response = client.post(
                        SENTINEL_HUB_PROCESS_URL,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "image/tiff"},
                        json=payload,
                    )
                    last_response = response
                    if response.status_code < 500 and response.status_code != 429:
                        break
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    last_error = exc
                if attempt < attempts - 1:
                    import time

                    time.sleep(self.settings.sentinel_retry_backoff_seconds * (2**attempt))
        if last_response is None:
            if last_error:
                raise last_error
            raise RuntimeError("Sentinel Hub Process API request failed without response.")
        if last_response.status_code >= 400:
            raise RuntimeError(f"Sentinel Hub Process API returned HTTP {last_response.status_code}: {self._process_api_error(last_response)}")
        return last_response

    def _read_process_api_tiff(self, content: bytes, region_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
        with MemoryFile(content) as memory_file:
            with memory_file.open() as dataset:
                if dataset.count < 5:
                    raise ValueError("Sentinel Hub Process API response did not include B04, B08, B12, SCL, and dataMask bands.")
                red = dataset.read(1).astype("float32")
                nir = dataset.read(2).astype("float32")
                swir2 = dataset.read(3).astype("float32")
                scl = dataset.read(4).astype("float32")
                data_mask = dataset.read(5).astype("float32")
                crs = dataset.crs or rasterio.crs.CRS.from_epsg(4326)
                transform = dataset.transform
                if transform.is_identity:
                    transform = from_bounds(*get_region_location(region_id).bounding_box(), dataset.width, dataset.height)
                profile = {**dataset.profile, "crs": crs, "transform": transform}
                return red, nir, swir2, scl, data_mask, profile

    def _normalize_process_reflectance(self, *bands: np.ndarray) -> tuple[np.ndarray, ...]:
        finite = np.concatenate([band[np.isfinite(band)] for band in bands])
        if finite.size and float(np.nanmax(finite)) > 3.0:
            return tuple(band / 10000.0 for band in bands)
        return bands

    def _process_api_evalscript(self) -> str:
        return """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "B12", "SCL", "dataMask"],
    output: { id: "default", bands: 5, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  return [sample.B04, sample.B08, sample.B12, sample.SCL, sample.dataMask];
}
"""

    def _process_api_error(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return str(payload.get("message") or payload.get("error") or payload)
        except Exception:
            pass
        return response.text[:300]

    def ndvi_status(self, region_id: str, scene_id: str | None = None) -> dict[str, Any]:
        try:
            region = get_region_location(region_id)
            scene = self.rasters._locate_scene(region.database_id, scene_id)
            if not scene:
                return self._status_payload(region.id, SentinelNDVIStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.")
            ndvi = (scene.metadata_json or {}).get("ndvi_processing") or {}
            stats = ndvi.get("statistics") or {}
            return {
                "region_id": region.id,
                "scene_id": scene.scene_id,
                "product_id": scene.product_id,
                "provider": scene.provider,
                "processing_status": ndvi.get("status", SentinelNDVIStatus.DISCOVERED),
                "quality_status": ndvi.get("quality_status", scene.quality_status),
                "processing_version": ndvi.get("processing_version", self.settings.sentinel_ndvi_processing_version),
                "mean": stats.get("mean"),
                "median": stats.get("median"),
                "min": stats.get("min"),
                "max": stats.get("max"),
                "standard_deviation": stats.get("standard_deviation"),
                "p10": stats.get("p10"),
                "p25": stats.get("p25"),
                "p50": stats.get("p50"),
                "p75": stats.get("p75"),
                "p90": stats.get("p90"),
                "valid_pixels": stats.get("valid_pixels"),
                "total_pixels": stats.get("total_pixels"),
                "valid_pixel_percentage": stats.get("valid_pixel_percentage"),
                "nbr_mean": (ndvi.get("nbr_statistics") or {}).get("mean"),
                "nbr_median": (ndvi.get("nbr_statistics") or {}).get("median"),
                "nbr_valid_pixels": (ndvi.get("nbr_statistics") or {}).get("valid_pixels"),
                "nbr_valid_pixel_percentage": (ndvi.get("nbr_statistics") or {}).get("valid_pixel_percentage"),
                "acquisition_time": scene.captured_at.isoformat() if scene.captured_at else None,
                "processed_at": ndvi.get("processed_at"),
                "available": ndvi.get("status") in {SentinelNDVIStatus.READY, SentinelNDVIStatus.LOW_QUALITY},
                "message": ndvi.get("message", "NDVI processing has not run for this scene."),
                "attribution": "Copernicus Data Space Ecosystem",
            }
        except ValueError:
            raise
        except Exception as exc:
            return self._status_payload(region_id, SentinelNDVIStatus.UNAVAILABLE, f"NDVI status is unavailable: {exc.__class__.__name__}.")

    def _prerequisite_error(self, scene: SatelliteImage) -> str | None:
        try:
            self.rasters._validate_scene(scene)
        except Exception as exc:
            return str(exc)
        metadata = scene.metadata_json or {}
        raster = metadata.get("raster_processing") or {}
        quality = metadata.get("quality_masking") or {}
        if raster.get("status") != SentinelRasterStatus.READY:
            return "Analysis-ready Sentinel raster preparation is not READY."
        if quality.get("status") not in {SentinelQualityMaskStatus.READY, SentinelQualityMaskStatus.LOW_QUALITY}:
            return "Sentinel quality mask is not READY."
        for label, key in {"analysis-ready": "manifest_path", "quality": "manifest_path"}.items():
            owner = raster if label == "analysis-ready" else quality
            path = owner.get(key)
            if not path or not Path(path).exists():
                return f"{label} manifest is missing."
        return None

    def _read_manifest(self, path: Path, label: str) -> dict[str, Any]:
        try:
            return json.loads(path.read_text())
        except Exception as exc:
            raise ValueError(f"Unable to read {label} manifest: {exc}") from exc

    def _process(
        self,
        scene: SatelliteImage,
        region_id: str,
        analysis_manifest_path: Path,
        quality_manifest_path: Path,
        analysis: dict[str, Any],
        quality: dict[str, Any],
        started_at: datetime,
    ) -> NDVISummary:
        red_path = self._resolve_path(analysis_manifest_path, analysis.get("output_references", {}).get("RED") or analysis.get("outputs", {}).get("RED"))
        nir_path = self._resolve_path(analysis_manifest_path, analysis.get("output_references", {}).get("NIR") or analysis.get("outputs", {}).get("NIR"))
        valid_mask_path = self._resolve_path(analysis_manifest_path, analysis.get("valid_mask"))
        quality_mask_path = self._resolve_path(quality_manifest_path, quality.get("quality_mask"))
        self._validate_band_mapping(analysis)

        output_dir = self.rasters._output_dir(scene, region_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        ndvi_path = output_dir / "ndvi.tif"
        ndvi_valid_mask_path = output_dir / "ndvi_valid_mask.tif"

        with rasterio.open(red_path) as red, rasterio.open(nir_path) as nir, rasterio.open(valid_mask_path) as valid_mask, rasterio.open(quality_mask_path) as quality_mask:
            self._validate_alignment({"RED": red, "NIR": nir, "valid_mask": valid_mask, "quality_mask": quality_mask})
            self._validate_reflectance_inputs(red, nir)
            profile = red.profile.copy()
            ndvi_profile = {**profile, "driver": "GTiff", "count": 1, "dtype": "float32", "nodata": NDVI_OUTPUT_NODATA, "compress": "deflate"}
            mask_profile = {**profile, "driver": "GTiff", "count": 1, "dtype": "uint8", "nodata": 0, "compress": "deflate"}
            valid_chunks: list[np.ndarray] = []
            total_pixels = red.width * red.height
            valid_pixels = 0

            with rasterio.open(ndvi_path, "w", **ndvi_profile) as ndvi_out, rasterio.open(ndvi_valid_mask_path, "w", **mask_profile) as mask_out:
                for _, window in red.block_windows(1):
                    red_data = red.read(1, window=window).astype("float32", copy=False)
                    nir_data = nir.read(1, window=window).astype("float32", copy=False)
                    raster_valid = valid_mask.read(1, window=window) == 1
                    quality_valid = quality_mask.read(1, window=window) == 1
                    ndvi_data, ndvi_valid = self._calculate_window(red_data, nir_data, raster_valid, quality_valid)
                    ndvi_out.write(ndvi_data, 1, window=window)
                    mask_out.write(ndvi_valid.astype("uint8"), 1, window=window)
                    if ndvi_valid.any():
                        values = ndvi_data[ndvi_valid].astype("float32", copy=True)
                        valid_chunks.append(values)
                        valid_pixels += int(values.size)

        if valid_pixels <= 0:
            raise ValueError("NDVI calculation produced no valid pixels.")
        stats = self._stats(total_pixels, valid_chunks)
        status = SentinelNDVIStatus.READY
        quality_status = DataQualityStatus.LIVE
        if stats.valid_pixel_percentage < self.settings.sentinel_min_valid_pixel_percent:
            status = SentinelNDVIStatus.LOW_QUALITY
            quality_status = DataQualityStatus.SUSPICIOUS
        completed_at = datetime.now(timezone.utc)
        provenance = {
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": NDVI_SOURCE_TYPE,
            "processing_version": self.settings.sentinel_ndvi_processing_version,
            "scene_id": scene.scene_id,
            "product_id": scene.product_id,
            "region_id": region_id,
            "formula": "(NIR - RED) / (NIR + RED)",
            "red_band": "B04",
            "nir_band": "B08",
            "input_reflectance": "Part 6D-1 physical surface reflectance rasters; no second scaling applied",
            "quality_mask_source": "Part 6D-2 Sentinel-2 L2A SCL quality_mask.tif",
            "analysis_manifest_path": str(analysis_manifest_path),
            "quality_manifest_path": str(quality_manifest_path),
            "input_paths": {"RED": str(red_path), "NIR": str(nir_path), "valid_mask": str(valid_mask_path), "quality_mask": str(quality_mask_path)},
            "ndvi_path": str(ndvi_path),
            "ndvi_valid_mask_path": str(ndvi_valid_mask_path),
            "nodata": NDVI_OUTPUT_NODATA,
            "zero_denominator": "masked_as_invalid",
            "range_validation": f"valid NDVI must be within [-1, 1] with tolerance {NDVI_RANGE_TOLERANCE}",
            "processing_started_at": started_at.isoformat(),
            "processed_at": completed_at.isoformat(),
            "low_quality_threshold_percent": self.settings.sentinel_min_valid_pixel_percent,
            "statistics": stats.to_dict(),
            "nbr": "unavailable_b12_required",
            "fire_risk_scoring": "not_implemented_in_part_6d_3",
        }
        summary = NDVISummary(
            region_id=region_id,
            scene_id=scene.scene_id or "",
            product_id=scene.product_id or "",
            acquisition_time=self.rasters._aware(scene.captured_at) or completed_at,
            processed_at=completed_at,
            status=status,
            quality_status=quality_status,
            processing_version=self.settings.sentinel_ndvi_processing_version,
            analysis_crs=analysis["analysis_crs"],
            resolution=tuple(analysis["resolution"]),
            width=int(analysis["width"]),
            height=int(analysis["height"]),
            transform=tuple(analysis["transform"]),
            ndvi_reference=str(ndvi_path),
            ndvi_valid_mask_reference=str(ndvi_valid_mask_path),
            stats=stats,
            vegetation_record_id=None,
            provenance=provenance,
        )
        manifest_path = output_dir / "ndvi_manifest.json"
        manifest_payload = summary.to_dict(expose_paths=True)
        manifest_payload["part"] = "6D-3 SENTINEL-2 NDVI PROCESSING - NBR and fire risk not implemented"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, default=str))
        summary.provenance["manifest_path"] = str(manifest_path)
        return summary

    def _calculate_window(self, red: np.ndarray, nir: np.ndarray, raster_valid: np.ndarray, quality_valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self._calculate_index_window(red, nir, raster_valid, quality_valid)

    def _calculate_index_window(self, lower_band: np.ndarray, upper_band: np.ndarray, raster_valid: np.ndarray, quality_valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        finite_inputs = np.isfinite(lower_band) & np.isfinite(upper_band)
        denominator = upper_band + lower_band
        denominator_valid = np.isfinite(denominator) & (np.abs(denominator) > 1e-12)
        preliminary_valid = raster_valid & quality_valid & finite_inputs & denominator_valid
        index = np.full(lower_band.shape, NDVI_OUTPUT_NODATA, dtype="float32")
        with np.errstate(divide="ignore", invalid="ignore"):
            calculated = (upper_band - lower_band) / denominator
        range_valid = np.isfinite(calculated) & (calculated >= -1.0 - NDVI_RANGE_TOLERANCE) & (calculated <= 1.0 + NDVI_RANGE_TOLERANCE)
        final_valid = preliminary_valid & range_valid
        index[final_valid] = np.clip(calculated[final_valid], -1.0, 1.0).astype("float32")
        return index, final_valid

    def _validate_band_mapping(self, analysis: dict[str, Any]) -> None:
        bands = analysis.get("bands") or {}
        for canonical, expected in NDVI_REQUIRED_BANDS.items():
            actual = (bands.get(canonical) or {}).get("source_identifier")
            if actual != expected:
                raise ValueError(f"NDVI requires {canonical} to be Sentinel-2 {expected}; found {actual or 'missing'}.")
        provenance = analysis.get("provenance") or {}
        if "scale_offset_handling" not in provenance:
            raise ValueError("Analysis-ready manifest lacks scale/offset provenance.")

    def _validate_alignment(self, datasets: dict[str, Any]) -> None:
        reference = datasets["RED"]
        ref_transform = (reference.transform.a, reference.transform.b, reference.transform.c, reference.transform.d, reference.transform.e, reference.transform.f)
        for name, dataset in datasets.items():
            if dataset.crs is None or dataset.crs != reference.crs:
                raise ValueError(f"{name} does not match RED CRS.")
            if dataset.width != reference.width or dataset.height != reference.height:
                raise ValueError(f"{name} does not match RED dimensions.")
            transform = (dataset.transform.a, dataset.transform.b, dataset.transform.c, dataset.transform.d, dataset.transform.e, dataset.transform.f)
            if not all(abs(actual - expected) <= 1e-6 for actual, expected in zip(transform, ref_transform)):
                raise ValueError(f"{name} does not match RED transform.")

    def _validate_reflectance_inputs(self, red: Any, nir: Any) -> None:
        for name, dataset in {"RED": red, "NIR": nir}.items():
            if dataset.dtypes[0] != "float32":
                raise ValueError(f"{name} input must be Part 6D-1 Float32 surface reflectance.")
            if dataset.nodata != NDVI_OUTPUT_NODATA:
                raise ValueError(f"{name} input nodata does not match the project raster nodata convention.")

    def _stats(self, total_pixels: int, chunks: list[np.ndarray]) -> NDVIStats:
        values = np.concatenate(chunks).astype("float32", copy=False)
        if not np.all(np.isfinite(values)):
            raise ValueError("NDVI statistics encountered non-finite values.")
        if np.any((values < -1.0 - NDVI_RANGE_TOLERANCE) | (values > 1.0 + NDVI_RANGE_TOLERANCE)):
            raise ValueError("NDVI statistics encountered values outside [-1, 1].")
        percentiles = np.percentile(values, [10, 25, 50, 75, 90])
        valid_pixels = int(values.size)
        return NDVIStats(
            total_pixels=total_pixels,
            valid_pixels=valid_pixels,
            invalid_pixels=total_pixels - valid_pixels,
            minimum=round(float(values.min()), 6),
            maximum=round(float(values.max()), 6),
            mean=round(float(values.mean()), 6),
            median=round(float(np.median(values)), 6),
            standard_deviation=round(float(values.std()), 6),
            percentiles={
                "p10": round(float(percentiles[0]), 6),
                "p25": round(float(percentiles[1]), 6),
                "p50": round(float(percentiles[2]), 6),
                "p75": round(float(percentiles[3]), 6),
                "p90": round(float(percentiles[4]), 6),
            },
        )

    def _rewrite_manifest(self, summary: NDVISummary) -> None:
        manifest_path = summary.provenance.get("manifest_path")
        if manifest_path:
            payload = summary.to_dict(expose_paths=True)
            payload["part"] = "6D-3 SENTINEL-2 NDVI PROCESSING - NBR and fire risk not implemented"
            Path(manifest_path).write_text(json.dumps(payload, indent=2, default=str))

    def _upsert_vegetation_record(self, scene: SatelliteImage, database_region_id: int, summary: NDVISummary) -> VegetationRecord:
        record = (
            self.db.query(VegetationRecord)
            .filter(
                VegetationRecord.region_id == database_region_id,
                VegetationRecord.provider == ProviderName.SENTINEL_2.value,
                VegetationRecord.product_id == scene.product_id,
                VegetationRecord.scene_id == scene.scene_id,
                VegetationRecord.processing_version == summary.processing_version,
            )
            .first()
        )
        if record is None:
            record = VegetationRecord(
                region_id=database_region_id,
                captured_at=summary.acquisition_time.replace(tzinfo=None),
                ndvi=summary.stats.mean if summary.stats.mean is not None else 0.0,
                nbr=summary.nbr_stats.mean if summary.nbr_stats and summary.nbr_stats.mean is not None else None,
                vegetation_health_index=None,
                satellite_source="Sentinel-2",
                cloud_percentage=scene.cloud_percentage,
                provider=ProviderName.SENTINEL_2.value,
                source_type=NDVI_SOURCE_TYPE,
                product_id=scene.product_id,
                scene_id=scene.scene_id,
                processing_version=summary.processing_version,
                processed_at=summary.processed_at.replace(tzinfo=None),
                quality_status=summary.quality_status.value,
                valid_pixel_percentage=summary.stats.valid_pixel_percentage,
                provenance_metadata={**summary._redacted_provenance(), "statistics": summary.stats.to_dict()},
            )
            self.db.add(record)
        else:
            record.captured_at = summary.acquisition_time.replace(tzinfo=None)
            record.ndvi = summary.stats.mean if summary.stats.mean is not None else record.ndvi
            record.nbr = summary.nbr_stats.mean if summary.nbr_stats and summary.nbr_stats.mean is not None else None
            record.vegetation_health_index = None
            record.cloud_percentage = scene.cloud_percentage
            record.source_type = NDVI_SOURCE_TYPE
            record.processed_at = summary.processed_at.replace(tzinfo=None)
            record.quality_status = summary.quality_status.value
            record.valid_pixel_percentage = summary.stats.valid_pixel_percentage
            record.provenance_metadata = {**summary._redacted_provenance(), "statistics": summary.stats.to_dict()}
        self.db.flush()
        return record

    def _with_record_id(self, summary: NDVISummary, record_id: int) -> NDVISummary:
        return NDVISummary(
            **{
                **summary.__dict__,
                "vegetation_record_id": record_id,
            }
        )

    def _resolve_path(self, manifest_path: Path, value: str | None) -> Path:
        if not value:
            raise FileNotFoundError("Required NDVI input path is missing from manifest.")
        path = Path(value)
        if not path.is_absolute():
            path = manifest_path.parent / path
        if not path.exists():
            raise FileNotFoundError(f"Required NDVI input file is missing: {path.name}.")
        return path

    def _cached_result(self, scene: SatelliteImage, region_id: str) -> NDVISummary | None:
        ndvi = (scene.metadata_json or {}).get("ndvi_processing") or {}
        if ndvi.get("status") not in {SentinelNDVIStatus.READY, SentinelNDVIStatus.LOW_QUALITY}:
            return None
        if ndvi.get("processing_version") != self.settings.sentinel_ndvi_processing_version:
            return None
        manifest_path = ndvi.get("manifest_path")
        ndvi_path = ndvi.get("ndvi_path")
        mask_path = ndvi.get("ndvi_valid_mask_path")
        if not manifest_path or not ndvi_path or not mask_path:
            return None
        if not Path(manifest_path).exists() or not Path(ndvi_path).exists() or not Path(mask_path).exists():
            return None
        payload = json.loads(Path(manifest_path).read_text())
        if (payload.get("provenance") or {}).get("source_api") == "sentinel_hub_process_api" and not payload.get("nbr_statistics"):
            return None
        stats_payload = payload["statistics"]
        stats = NDVIStats(
            total_pixels=int(stats_payload["total_pixels"]),
            valid_pixels=int(stats_payload["valid_pixels"]),
            invalid_pixels=int(stats_payload["invalid_pixels"]),
            minimum=stats_payload.get("min"),
            maximum=stats_payload.get("max"),
            mean=stats_payload.get("mean"),
            median=stats_payload.get("median"),
            standard_deviation=stats_payload.get("standard_deviation"),
            percentiles={key: stats_payload.get(key) for key in ["p10", "p25", "p50", "p75", "p90"]},
        )
        return NDVISummary(
            region_id=region_id,
            scene_id=payload["scene_id"],
            product_id=payload["product_id"],
            acquisition_time=datetime.fromisoformat(payload["acquisition_time"]),
            processed_at=datetime.fromisoformat(payload["processed_at"]),
            status=payload["status"],
            quality_status=DataQualityStatus(payload["quality_status"]),
            processing_version=payload["processing_version"],
            analysis_crs=payload["analysis_crs"],
            resolution=tuple(payload["resolution"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            transform=tuple(payload["transform"]),
            ndvi_reference=payload["ndvi"],
            ndvi_valid_mask_reference=payload["ndvi_valid_mask"],
            stats=stats,
            vegetation_record_id=payload.get("vegetation_record_id"),
            provenance=payload.get("provenance", {}),
            nbr_reference=payload.get("nbr"),
            nbr_valid_mask_reference=payload.get("nbr_valid_mask"),
            nbr_stats=NDVIStats(
                total_pixels=int(payload["nbr_statistics"]["total_pixels"]),
                valid_pixels=int(payload["nbr_statistics"]["valid_pixels"]),
                invalid_pixels=int(payload["nbr_statistics"]["invalid_pixels"]),
                minimum=payload["nbr_statistics"].get("min"),
                maximum=payload["nbr_statistics"].get("max"),
                mean=payload["nbr_statistics"].get("mean"),
                median=payload["nbr_statistics"].get("median"),
                standard_deviation=payload["nbr_statistics"].get("standard_deviation"),
                percentiles={key: payload["nbr_statistics"].get(key) for key in ["p10", "p25", "p50", "p75", "p90"]},
            )
            if payload.get("nbr_statistics")
            else None,
        )

    def _set_processing_state(self, scene: SatelliteImage, status: str, started_at: datetime | None = None, summary: NDVISummary | None = None, message: str | None = None) -> None:
        metadata = dict(scene.metadata_json or {})
        ndvi = dict(metadata.get("ndvi_processing") or {})
        ndvi.update(
            {
                "status": status,
                "message": message or ("NDVI processing complete." if status in {SentinelNDVIStatus.READY, SentinelNDVIStatus.LOW_QUALITY} else "NDVI processing in progress."),
                "started_at": started_at.isoformat() if started_at else ndvi.get("started_at"),
                "processing_version": self.settings.sentinel_ndvi_processing_version,
            }
        )
        if summary:
            ndvi.update(
                {
                    "quality_status": summary.quality_status.value,
                    "statistics": summary.stats.to_dict(),
                    "ndvi_path": summary.ndvi_reference,
                    "ndvi_valid_mask_path": summary.ndvi_valid_mask_reference,
                    "nbr_path": summary.nbr_reference,
                    "nbr_valid_mask_path": summary.nbr_valid_mask_reference,
                    "manifest_path": summary.provenance.get("manifest_path"),
                    "vegetation_record_id": summary.vegetation_record_id,
                    "processed_at": summary.processed_at.isoformat(),
                    "analysis_crs": summary.analysis_crs,
                    "resolution": summary.resolution,
                    "width": summary.width,
                    "height": summary.height,
                    "nbr_statistics": summary.nbr_stats.to_dict() if summary.nbr_stats else None,
                }
            )
        metadata["ndvi_processing"] = ndvi
        scene.metadata_json = metadata
        self.db.flush()

    def _set_failure_state(self, scene: SatelliteImage, started_at: datetime, message: str) -> None:
        try:
            metadata = dict(scene.metadata_json or {})
            metadata["ndvi_processing"] = {
                **dict(metadata.get("ndvi_processing") or {}),
                "status": SentinelNDVIStatus.FAILED,
                "message": message,
                "started_at": started_at.isoformat(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "processing_version": self.settings.sentinel_ndvi_processing_version,
            }
            scene.metadata_json = metadata
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _failure(self, status: str, message: str, kind: ProviderErrorKind) -> NDVIResult:
        return NDVIResult(status, DataQualityStatus.UNAVAILABLE, None, NDVIError(kind, message))

    def _status_payload(self, region_id: str, status: str, message: str) -> dict[str, Any]:
        return {
            "region_id": region_id,
            "scene_id": None,
            "product_id": None,
            "provider": ProviderName.SENTINEL_2.value,
            "processing_status": status,
            "quality_status": DataQualityStatus.UNAVAILABLE.value,
            "processing_version": self.settings.sentinel_ndvi_processing_version,
            "mean": None,
            "median": None,
            "nbr_mean": None,
            "nbr_median": None,
            "nbr_valid_pixels": None,
            "nbr_valid_pixel_percentage": None,
            "min": None,
            "max": None,
            "standard_deviation": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "valid_pixels": None,
            "total_pixels": None,
            "valid_pixel_percentage": None,
            "acquisition_time": None,
            "processed_at": None,
            "available": False,
            "message": message,
            "attribution": "Copernicus Data Space Ecosystem",
        }
