from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.database.models import SatelliteImage
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind, ProviderName, classify_provider_error
from backend.services.region_registry import get_region_location
from backend.services.sentinel_provider import SentinelAcquisitionStatus
from backend.services.sentinel_raster_service import SentinelRasterService, SentinelRasterStatus

QUALITY_MASK_SOURCE_TYPE = "sentinel2_l2a_scl_quality_masking"
QUALITY_MASK_NODATA = 0
QUALITY_MASK_VALID = 1

SCL_CLASSES = {
    0: {"label": "NO_DATA", "category": "invalid", "valid": False},
    1: {"label": "SATURATED_OR_DEFECTIVE", "category": "invalid", "valid": False},
    2: {"label": "CAST_SHADOWS", "category": "shadow", "valid": False},
    3: {"label": "CLOUD_SHADOWS", "category": "shadow", "valid": False},
    4: {"label": "VEGETATION", "category": "valid", "valid": True},
    5: {"label": "NOT_VEGETATED", "category": "valid", "valid": True},
    6: {"label": "WATER", "category": "invalid", "valid": False},
    7: {"label": "UNCLASSIFIED", "category": "invalid", "valid": False},
    8: {"label": "CLOUD_MEDIUM_PROBABILITY", "category": "cloud", "valid": False},
    9: {"label": "CLOUD_HIGH_PROBABILITY", "category": "cloud", "valid": False},
    10: {"label": "THIN_CIRRUS", "category": "cirrus", "valid": False},
    11: {"label": "SNOW_OR_ICE", "category": "snow", "valid": False},
}
VALID_SCL_CLASSES = {4, 5}
CLOUD_SCL_CLASSES = {8, 9}
SHADOW_SCL_CLASSES = {2, 3}
CIRRUS_SCL_CLASSES = {10}
SNOW_SCL_CLASSES = {11}
INVALID_SCL_CLASSES = {0, 1, 6, 7}


class SentinelQualityMaskStatus:
    DISCOVERED = "DISCOVERED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    LOW_QUALITY = "LOW_QUALITY"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class QualityMaskError:
    kind: ProviderErrorKind
    message: str


@dataclass(frozen=True)
class QualityLayer:
    source_identifier: str
    path_reference: str
    native_resolution: tuple[float, float]
    crs: str
    width: int
    height: int
    dtype: str
    nodata: float | int | None

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "source_identifier": self.source_identifier,
            "path_reference": self.path_reference if expose_paths else Path(self.path_reference).name,
            "native_resolution": self.native_resolution,
            "crs": self.crs,
            "width": self.width,
            "height": self.height,
            "dtype": self.dtype,
            "nodata": self.nodata,
        }


@dataclass(frozen=True)
class QualityMaskStats:
    total_pixels: int
    valid_pixels: int
    masked_pixels: int
    cloud_pixels: int
    shadow_pixels: int
    cirrus_pixels: int
    snow_pixels: int
    invalid_pixels: int
    class_counts: dict[str, int] = field(default_factory=dict)

    @property
    def valid_pixel_percentage(self) -> float:
        return self._percentage(self.valid_pixels)

    @property
    def masked_pixel_percentage(self) -> float:
        return self._percentage(self.masked_pixels)

    @property
    def cloud_percentage(self) -> float:
        return self._percentage(self.cloud_pixels)

    @property
    def shadow_percentage(self) -> float:
        return self._percentage(self.shadow_pixels)

    @property
    def cirrus_percentage(self) -> float:
        return self._percentage(self.cirrus_pixels)

    @property
    def snow_percentage(self) -> float:
        return self._percentage(self.snow_pixels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_pixels": self.total_pixels,
            "valid_pixels": self.valid_pixels,
            "masked_pixels": self.masked_pixels,
            "valid_pixel_percentage": self.valid_pixel_percentage,
            "masked_pixel_percentage": self.masked_pixel_percentage,
            "cloud_pixels": self.cloud_pixels,
            "cloud_percentage": self.cloud_percentage,
            "shadow_pixels": self.shadow_pixels,
            "shadow_percentage": self.shadow_percentage,
            "cirrus_pixels": self.cirrus_pixels,
            "cirrus_percentage": self.cirrus_percentage,
            "snow_pixels": self.snow_pixels,
            "snow_percentage": self.snow_percentage,
            "invalid_pixels": self.invalid_pixels,
            "class_counts": self.class_counts,
        }

    def _percentage(self, value: int) -> float:
        if self.total_pixels <= 0:
            return 0.0
        return round((value / self.total_pixels) * 100, 2)


@dataclass(frozen=True)
class QualityMask:
    region_id: str
    scene_id: str
    product_id: str
    status: str
    quality_status: DataQualityStatus
    masking_version: str
    processing_started_at: datetime
    processing_completed_at: datetime
    analysis_crs: str
    resolution: tuple[float, float]
    width: int
    height: int
    transform: tuple[float, float, float, float, float, float]
    quality_layer: QualityLayer
    quality_mask_reference: str
    quality_class_reference: str
    stats: QualityMaskStats
    provenance: dict[str, Any]

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "scene_id": self.scene_id,
            "product_id": self.product_id,
            "status": self.status,
            "quality_status": self.quality_status.value,
            "masking_version": self.masking_version,
            "processing_started_at": self.processing_started_at.isoformat(),
            "processing_completed_at": self.processing_completed_at.isoformat(),
            "analysis_crs": self.analysis_crs,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "transform": self.transform,
            "quality_layer": self.quality_layer.to_dict(expose_paths=expose_paths),
            "quality_mask": self.quality_mask_reference if expose_paths else Path(self.quality_mask_reference).name,
            "quality_class": self.quality_class_reference if expose_paths else Path(self.quality_class_reference).name,
            "stats": self.stats.to_dict(),
            "provenance": self.provenance if expose_paths else self._redacted_provenance(),
        }

    def _redacted_provenance(self) -> dict[str, Any]:
        return {key: value for key, value in self.provenance.items() if key not in {"manifest_path", "quality_mask_path", "quality_class_path", "analysis_manifest_path"}}


@dataclass(frozen=True)
class QualityMaskResult:
    status: str
    quality_status: DataQualityStatus
    mask: QualityMask | None = None
    error: QualityMaskError | None = None

    @property
    def ok(self) -> bool:
        return self.status in {SentinelQualityMaskStatus.READY, SentinelQualityMaskStatus.LOW_QUALITY} and self.mask is not None

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "quality_status": self.quality_status.value,
            "mask": self.mask.to_dict(expose_paths=expose_paths) if self.mask else None,
            "error": {"kind": self.error.kind.value, "message": self.error.message} if self.error else None,
        }


class SentinelQualityMaskService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.rasters = SentinelRasterService(db, settings=self.settings)

    def apply_quality_mask(self, region_id: str, scene_id: str | None = None) -> QualityMaskResult:
        started_at = datetime.now(timezone.utc)
        scene: SatelliteImage | None = None
        try:
            region = get_region_location(region_id)
            scene = self.rasters._locate_scene(region.database_id, scene_id)
            if not scene:
                return self._failure(SentinelQualityMaskStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.", ProviderErrorKind.CONFIGURATION_ERROR)
            cached = self._cached_result(scene, region.id)
            if cached:
                return QualityMaskResult(cached.status, cached.quality_status, cached)
            self.rasters._validate_scene(scene)
            raster_metadata = (scene.metadata_json or {}).get("raster_processing") or {}
            if raster_metadata.get("status") != SentinelRasterStatus.READY:
                return self._failure(
                    SentinelQualityMaskStatus.UNAVAILABLE,
                    "Analysis-ready Sentinel bands are not READY; run raster preparation before quality masking.",
                    ProviderErrorKind.CONFIGURATION_ERROR,
                )
            analysis_manifest_path = raster_metadata.get("manifest_path")
            if not analysis_manifest_path or not Path(analysis_manifest_path).exists():
                raise FileNotFoundError("Analysis-ready Sentinel manifest is missing.")

            self._set_processing_state(scene, SentinelQualityMaskStatus.PROCESSING, started_at=started_at)
            product = self.rasters._open_product(Path(scene.storage_reference or ""))
            quality_layer = self._discover_quality_layer(product)
            analysis = self._read_analysis_manifest(Path(analysis_manifest_path))
            mask = self._process(scene, region.id, product, quality_layer, analysis, Path(analysis_manifest_path), started_at)
            self._set_processing_state(scene, mask.status, started_at=started_at, mask=mask)
            self.db.commit()
            return QualityMaskResult(mask.status, mask.quality_status, mask)
        except Exception as exc:
            self.db.rollback()
            if scene is not None:
                self._set_failure_state(scene, started_at, str(exc))
            return self._failure(SentinelQualityMaskStatus.FAILED, str(exc), classify_provider_error(exc))

    def quality_status(self, region_id: str, scene_id: str | None = None) -> dict[str, Any]:
        try:
            region = get_region_location(region_id)
            scene = self.rasters._locate_scene(region.database_id, scene_id)
            if not scene:
                return self._status_payload(region.id, SentinelQualityMaskStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.")
            quality = (scene.metadata_json or {}).get("quality_masking") or {}
            stats = quality.get("stats") or {}
            return {
                "region_id": region.id,
                "scene_id": scene.scene_id,
                "product_id": scene.product_id,
                "provider": scene.provider,
                "acquisition_status": scene.acquisition_status,
                "processing_status": quality.get("status", SentinelQualityMaskStatus.DISCOVERED),
                "quality_status": quality.get("quality_status", scene.quality_status),
                "masking_version": quality.get("masking_version", self.settings.sentinel_quality_mask_version),
                "valid_pixel_percentage": stats.get("valid_pixel_percentage"),
                "masked_pixel_percentage": stats.get("masked_pixel_percentage"),
                "cloud_percentage": stats.get("cloud_percentage"),
                "shadow_percentage": stats.get("shadow_percentage"),
                "cirrus_percentage": stats.get("cirrus_percentage"),
                "snow_percentage": stats.get("snow_percentage"),
                "processed_at": quality.get("completed_at"),
                "available": quality.get("status") in {SentinelQualityMaskStatus.READY, SentinelQualityMaskStatus.LOW_QUALITY},
                "message": quality.get("message", "Quality masking has not run for this scene."),
                "attribution": "Copernicus Data Space Ecosystem",
            }
        except ValueError:
            raise
        except Exception as exc:
            return self._status_payload(region_id, SentinelQualityMaskStatus.UNAVAILABLE, f"Quality mask status is unavailable: {exc.__class__.__name__}.")

    def _discover_quality_layer(self, product: dict[str, Any]) -> QualityLayer:
        member = self._find_scl_member(product)
        if member is None:
            raise FileNotFoundError("Sentinel-2 L2A SCL quality layer is missing; quality mask was not generated.")
        dataset_path = self.rasters._dataset_path(product, member)
        try:
            with rasterio.open(dataset_path) as dataset:
                if not dataset.crs:
                    raise ValueError("Sentinel-2 SCL quality layer is missing CRS.")
                transform = dataset.transform
                return QualityLayer(
                    source_identifier="SCL",
                    path_reference=dataset_path,
                    native_resolution=(abs(transform.a), abs(transform.e)),
                    crs=dataset.crs.to_string(),
                    width=dataset.width,
                    height=dataset.height,
                    dtype=dataset.dtypes[0],
                    nodata=dataset.nodata,
                )
        except RasterioIOError as exc:
            raise ValueError(f"Unable to read Sentinel-2 SCL quality layer: {exc}") from exc

    def _find_scl_member(self, product: dict[str, Any]) -> Any | None:
        pattern = re.compile(r"(^|[_/])SCL(_(?:10|20|60)m)?\.(jp2|tif|tiff)$", re.IGNORECASE)
        matches = [member for member in product["members"] if pattern.search(str(member))]
        if not matches:
            return None
        preferred = [member for member in matches if "_20m" in str(member).lower() or "/r20m/" in str(member).lower()]
        return sorted(preferred or matches, key=lambda item: str(item))[0]

    def _read_analysis_manifest(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text())
        required = {"analysis_crs", "resolution", "transform", "width", "height", "outputs", "valid_mask"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Analysis-ready manifest is missing required fields: {', '.join(missing)}.")
        return payload

    def _process(
        self,
        scene: SatelliteImage,
        region_id: str,
        product: dict[str, Any],
        quality_layer: QualityLayer,
        analysis: dict[str, Any],
        analysis_manifest_path: Path,
        started_at: datetime,
    ) -> QualityMask:
        width = int(analysis["width"])
        height = int(analysis["height"])
        analysis_crs = analysis["analysis_crs"]
        analysis_transform = Affine(*analysis["transform"])
        self._validate_analysis_alignment(analysis, analysis_manifest_path)
        valid_mask_path = analysis_manifest_path.parent / analysis["valid_mask"]
        output_dir = self.rasters._output_dir(scene, region_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        with rasterio.open(valid_mask_path) as valid_dataset:
            raster_valid = valid_dataset.read(1) == 1
            profile = valid_dataset.profile.copy()

        with rasterio.open(quality_layer.path_reference) as source:
            with WarpedVRT(
                source,
                crs=analysis_crs,
                transform=analysis_transform,
                width=width,
                height=height,
                resampling=Resampling.nearest,
                src_nodata=source.nodata,
                dst_nodata=QUALITY_MASK_NODATA,
            ) as vrt:
                scl = vrt.read(1, out_shape=(height, width), masked=False).astype("uint8")

        scl_valid = np.isin(scl, list(VALID_SCL_CLASSES))
        clean_mask = (raster_valid & scl_valid).astype("uint8")
        stats = self._stats(scl, clean_mask, raster_valid)
        completed_at = datetime.now(timezone.utc)
        status = SentinelQualityMaskStatus.READY
        quality_status = DataQualityStatus.LIVE
        if stats.valid_pixel_percentage < self.settings.sentinel_min_valid_pixel_percent:
            status = SentinelQualityMaskStatus.LOW_QUALITY
            quality_status = DataQualityStatus.SUSPICIOUS

        quality_mask_path = output_dir / "quality_mask.tif"
        quality_class_path = output_dir / "quality_class_scl.tif"
        write_profile = {**profile, "driver": "GTiff", "height": height, "width": width, "count": 1, "dtype": "uint8", "nodata": QUALITY_MASK_NODATA, "compress": "deflate"}
        with rasterio.open(quality_mask_path, "w", **write_profile) as destination:
            destination.write(clean_mask, 1)
        with rasterio.open(quality_class_path, "w", **write_profile) as destination:
            destination.write(scl, 1)

        provenance = {
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": QUALITY_MASK_SOURCE_TYPE,
            "masking_version": self.settings.sentinel_quality_mask_version,
            "scene_id": scene.scene_id,
            "product_id": scene.product_id,
            "region_id": region_id,
            "scl_mapping": SCL_CLASSES,
            "valid_scl_classes": sorted(VALID_SCL_CLASSES),
            "cloud_scl_classes": sorted(CLOUD_SCL_CLASSES),
            "shadow_scl_classes": sorted(SHADOW_SCL_CLASSES),
            "cirrus_scl_classes": sorted(CIRRUS_SCL_CLASSES),
            "snow_scl_classes": sorted(SNOW_SCL_CLASSES),
            "invalid_scl_classes": sorted(INVALID_SCL_CLASSES),
            "resampling_method": "nearest_for_categorical_scl",
            "analysis_manifest_path": str(analysis_manifest_path),
            "quality_mask_path": str(quality_mask_path),
            "quality_class_path": str(quality_class_path),
            "processing_started_at": started_at.isoformat(),
            "processing_completed_at": completed_at.isoformat(),
            "low_quality_threshold_percent": self.settings.sentinel_min_valid_pixel_percent,
            "no_synthetic_masks": True,
            "downstream_indices": "not_implemented_in_part_6d_2",
        }
        mask = QualityMask(
            region_id=region_id,
            scene_id=scene.scene_id or "",
            product_id=scene.product_id or "",
            status=status,
            quality_status=quality_status,
            masking_version=self.settings.sentinel_quality_mask_version,
            processing_started_at=started_at,
            processing_completed_at=completed_at,
            analysis_crs=analysis_crs,
            resolution=tuple(analysis["resolution"]),
            width=width,
            height=height,
            transform=tuple(analysis["transform"]),
            quality_layer=quality_layer,
            quality_mask_reference=str(quality_mask_path),
            quality_class_reference=str(quality_class_path),
            stats=stats,
            provenance=provenance,
        )
        manifest_path = output_dir / "quality_manifest.json"
        manifest_payload = mask.to_dict(expose_paths=True)
        manifest_payload["part"] = "6D-2 SENTINEL-2 SCL QUALITY MASKING - NDVI and NBR not implemented"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, default=str))
        mask.provenance["manifest_path"] = str(manifest_path)
        return mask

    def _validate_analysis_alignment(self, analysis: dict[str, Any], analysis_manifest_path: Path) -> None:
        expected_crs = analysis["analysis_crs"]
        expected_transform = tuple(analysis["transform"])
        expected_width = int(analysis["width"])
        expected_height = int(analysis["height"])
        paths = dict(analysis.get("output_references") or analysis.get("outputs") or {})
        paths["valid_mask"] = str(analysis_manifest_path.parent / analysis["valid_mask"])
        for name, path in paths.items():
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = analysis_manifest_path.parent / candidate
            if not candidate.exists():
                raise FileNotFoundError(f"Analysis-ready raster {name} is missing.")
            with rasterio.open(candidate) as dataset:
                if dataset.crs is None or dataset.crs.to_string() != expected_crs:
                    raise ValueError(f"Analysis-ready raster {name} does not match the analysis CRS.")
                if dataset.width != expected_width or dataset.height != expected_height:
                    raise ValueError(f"Analysis-ready raster {name} does not match the analysis dimensions.")
                actual_transform = (dataset.transform.a, dataset.transform.b, dataset.transform.c, dataset.transform.d, dataset.transform.e, dataset.transform.f)
                if not all(abs(actual - expected) <= 1e-6 for actual, expected in zip(actual_transform, expected_transform)):
                    raise ValueError(f"Analysis-ready raster {name} does not match the analysis transform.")

    def _stats(self, scl: np.ndarray, clean_mask: np.ndarray, raster_valid: np.ndarray) -> QualityMaskStats:
        total = int(scl.size)
        valid = int(clean_mask.sum())
        class_counts = {str(code): int(np.count_nonzero(scl == code)) for code in sorted(SCL_CLASSES)}
        cloud = int(sum(class_counts[str(code)] for code in CLOUD_SCL_CLASSES))
        shadow = int(sum(class_counts[str(code)] for code in SHADOW_SCL_CLASSES))
        cirrus = int(sum(class_counts[str(code)] for code in CIRRUS_SCL_CLASSES))
        snow = int(sum(class_counts[str(code)] for code in SNOW_SCL_CLASSES))
        invalid = int(np.count_nonzero((~raster_valid) | np.isin(scl, list(INVALID_SCL_CLASSES))))
        return QualityMaskStats(
            total_pixels=total,
            valid_pixels=valid,
            masked_pixels=total - valid,
            cloud_pixels=cloud,
            shadow_pixels=shadow,
            cirrus_pixels=cirrus,
            snow_pixels=snow,
            invalid_pixels=invalid,
            class_counts=class_counts,
        )

    def _cached_result(self, scene: SatelliteImage, region_id: str) -> QualityMask | None:
        quality = (scene.metadata_json or {}).get("quality_masking") or {}
        if quality.get("status") not in {SentinelQualityMaskStatus.READY, SentinelQualityMaskStatus.LOW_QUALITY}:
            return None
        if quality.get("masking_version") != self.settings.sentinel_quality_mask_version:
            return None
        manifest_path = quality.get("manifest_path")
        mask_path = quality.get("quality_mask_path")
        class_path = quality.get("quality_class_path")
        if not manifest_path or not mask_path or not class_path:
            return None
        if not Path(manifest_path).exists() or not Path(mask_path).exists() or not Path(class_path).exists():
            return None
        payload = json.loads(Path(manifest_path).read_text())
        stats = QualityMaskStats(
            total_pixels=int(payload["stats"]["total_pixels"]),
            valid_pixels=int(payload["stats"]["valid_pixels"]),
            masked_pixels=int(payload["stats"]["masked_pixels"]),
            cloud_pixels=int(payload["stats"]["cloud_pixels"]),
            shadow_pixels=int(payload["stats"]["shadow_pixels"]),
            cirrus_pixels=int(payload["stats"]["cirrus_pixels"]),
            snow_pixels=int(payload["stats"]["snow_pixels"]),
            invalid_pixels=int(payload["stats"]["invalid_pixels"]),
            class_counts={str(key): int(value) for key, value in payload["stats"].get("class_counts", {}).items()},
        )
        return QualityMask(
            region_id=region_id,
            scene_id=payload["scene_id"],
            product_id=payload["product_id"],
            status=payload["status"],
            quality_status=DataQualityStatus(payload["quality_status"]),
            masking_version=payload["masking_version"],
            processing_started_at=datetime.fromisoformat(payload["processing_started_at"]),
            processing_completed_at=datetime.fromisoformat(payload["processing_completed_at"]),
            analysis_crs=payload["analysis_crs"],
            resolution=tuple(payload["resolution"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            transform=tuple(payload["transform"]),
            quality_layer=QualityLayer(**payload["quality_layer"]),
            quality_mask_reference=payload["quality_mask"],
            quality_class_reference=payload["quality_class"],
            stats=stats,
            provenance=payload.get("provenance", {}),
        )

    def _set_processing_state(self, scene: SatelliteImage, status: str, started_at: datetime | None = None, mask: QualityMask | None = None, message: str | None = None) -> None:
        metadata = dict(scene.metadata_json or {})
        quality = dict(metadata.get("quality_masking") or {})
        quality.update(
            {
                "status": status,
                "message": message or ("Quality masking complete." if status in {SentinelQualityMaskStatus.READY, SentinelQualityMaskStatus.LOW_QUALITY} else "Quality masking in progress."),
                "started_at": started_at.isoformat() if started_at else quality.get("started_at"),
                "masking_version": self.settings.sentinel_quality_mask_version,
            }
        )
        if mask:
            quality.update(
                {
                    "quality_status": mask.quality_status.value,
                    "quality_source": "SCL",
                    "quality_mask_path": mask.quality_mask_reference,
                    "quality_class_path": mask.quality_class_reference,
                    "manifest_path": mask.provenance.get("manifest_path"),
                    "stats": mask.stats.to_dict(),
                    "analysis_crs": mask.analysis_crs,
                    "resolution": mask.resolution,
                    "width": mask.width,
                    "height": mask.height,
                    "completed_at": mask.processing_completed_at.isoformat(),
                }
            )
        metadata["quality_masking"] = quality
        scene.metadata_json = metadata
        self.db.flush()

    def _set_failure_state(self, scene: SatelliteImage, started_at: datetime, message: str) -> None:
        try:
            metadata = dict(scene.metadata_json or {})
            metadata["quality_masking"] = {
                **dict(metadata.get("quality_masking") or {}),
                "status": SentinelQualityMaskStatus.FAILED,
                "message": message,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "masking_version": self.settings.sentinel_quality_mask_version,
            }
            scene.metadata_json = metadata
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _failure(self, status: str, message: str, kind: ProviderErrorKind) -> QualityMaskResult:
        return QualityMaskResult(status, DataQualityStatus.UNAVAILABLE, None, QualityMaskError(kind, message))

    def _status_payload(self, region_id: str, status: str, message: str) -> dict[str, Any]:
        return {
            "region_id": region_id,
            "scene_id": None,
            "product_id": None,
            "provider": ProviderName.SENTINEL_2.value,
            "acquisition_status": SentinelAcquisitionStatus.UNAVAILABLE,
            "processing_status": status,
            "quality_status": DataQualityStatus.UNAVAILABLE.value,
            "masking_version": self.settings.sentinel_quality_mask_version,
            "valid_pixel_percentage": None,
            "masked_pixel_percentage": None,
            "cloud_percentage": None,
            "shadow_percentage": None,
            "cirrus_percentage": None,
            "snow_percentage": None,
            "processed_at": None,
            "available": False,
            "message": message,
            "attribution": "Copernicus Data Space Ecosystem",
        }
