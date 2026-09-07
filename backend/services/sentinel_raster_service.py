from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from defusedxml import ElementTree
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.io import DatasetReader
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds
from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.database.models import SatelliteImage
from backend.repositories.environment import SatelliteImageRepository
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind, ProviderName, classify_provider_error
from backend.services.region_registry import get_region_location
from backend.services.sentinel_provider import SentinelAcquisitionStatus

CANONICAL_BANDS = {
    "RED": {"sentinel_id": "B04", "native_resolution_m": 10, "purpose": "future_ndvi_red"},
    "NIR": {"sentinel_id": "B08", "native_resolution_m": 10, "purpose": "future_ndvi_nir_and_nbr_nir"},
    "SWIR": {"sentinel_id": "B11", "native_resolution_m": 20, "purpose": "future_nbr_swir"},
}
PROCESSING_SOURCE_TYPE = "sentinel2_l2a_raster_band_preparation"
PROCESSING_OUTPUT_NODATA = -9999.0


class SentinelRasterStatus:
    DISCOVERED = "DISCOVERED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class RasterProcessingError:
    kind: ProviderErrorKind
    message: str


@dataclass(frozen=True)
class RasterScale:
    quantification_value: float = 1.0
    offset: float = 0.0
    source: str = "identity"

    def to_dict(self) -> dict[str, Any]:
        return {"quantification_value": self.quantification_value, "offset": self.offset, "source": self.source}


@dataclass(frozen=True)
class SpectralBand:
    name: str
    source_identifier: str
    path_reference: str
    native_resolution: tuple[float, float]
    crs: str
    transform: tuple[float, float, float, float, float, float]
    width: int
    height: int
    bounds: tuple[float, float, float, float]
    dtype: str
    nodata: float | int | None
    scale: RasterScale

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_identifier": self.source_identifier,
            "native_resolution": self.native_resolution,
            "crs": self.crs,
            "transform": self.transform,
            "width": self.width,
            "height": self.height,
            "bounds": self.bounds,
            "dtype": self.dtype,
            "nodata": self.nodata,
            "scale": self.scale.to_dict(),
        }


@dataclass(frozen=True)
class AnalysisReadyBands:
    region_id: str
    scene_id: str
    product_id: str
    acquisition_time: datetime
    retrieved_at: datetime | None
    processing_started_at: datetime
    processing_completed_at: datetime
    processing_status: str
    quality_status: DataQualityStatus
    analysis_crs: str
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    transform: tuple[float, float, float, float, float, float]
    bands: dict[str, SpectralBand]
    output_references: dict[str, str]
    valid_mask_reference: str
    valid_pixel_count: int
    total_pixel_count: int
    provenance: dict[str, Any]

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        output_refs = self.output_references if expose_paths else {band: Path(path).name for band, path in self.output_references.items()}
        return {
            "region_id": self.region_id,
            "scene_id": self.scene_id,
            "product_id": self.product_id,
            "acquisition_time": self.acquisition_time.isoformat(),
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "processing_started_at": self.processing_started_at.isoformat(),
            "processing_completed_at": self.processing_completed_at.isoformat(),
            "processing_status": self.processing_status,
            "quality_status": self.quality_status.value,
            "analysis_crs": self.analysis_crs,
            "resolution": self.resolution,
            "bounds": self.bounds,
            "width": self.width,
            "height": self.height,
            "transform": self.transform,
            "available_bands": sorted(self.bands),
            "bands": {name: band.to_dict() for name, band in self.bands.items()},
            "outputs": output_refs,
            "valid_mask": Path(self.valid_mask_reference).name if not expose_paths else self.valid_mask_reference,
            "valid_pixel_count": self.valid_pixel_count,
            "total_pixel_count": self.total_pixel_count,
            "provenance": self.provenance if expose_paths else self._redacted_provenance(),
        }

    def _redacted_provenance(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.provenance.items()
            if key not in {"output_references", "source_paths", "manifest_path"}
        }


@dataclass(frozen=True)
class RasterProcessingResult:
    status: str
    quality_status: DataQualityStatus
    analysis_ready: AnalysisReadyBands | None = None
    error: RasterProcessingError | None = None

    @property
    def ok(self) -> bool:
        return self.status == SentinelRasterStatus.READY and self.analysis_ready is not None

    def to_dict(self, expose_paths: bool = False) -> dict[str, Any]:
        return {
            "status": self.status,
            "quality_status": self.quality_status.value,
            "analysis_ready": self.analysis_ready.to_dict(expose_paths=expose_paths) if self.analysis_ready else None,
            "error": {"kind": self.error.kind.value, "message": self.error.message} if self.error else None,
        }


class SentinelRasterService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.scenes = SatelliteImageRepository(db)

    def prepare_analysis_ready_bands(self, region_id: str, scene_id: str | None = None) -> RasterProcessingResult:
        started_at = datetime.now(timezone.utc)
        scene: SatelliteImage | None = None
        try:
            region = get_region_location(region_id)
            scene = self._locate_scene(region.database_id, scene_id)
            if not scene:
                return self._failure(SentinelRasterStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.", ProviderErrorKind.CONFIGURATION_ERROR)
            cached = self._cached_result(scene, region.id)
            if cached:
                return RasterProcessingResult(SentinelRasterStatus.READY, DataQualityStatus(scene.quality_status), cached)
            self._set_processing_state(scene, SentinelRasterStatus.VALIDATING, started_at=started_at)
            self._validate_scene(scene)
            product = self._open_product(Path(scene.storage_reference or ""))
            metadata = self._read_product_metadata(product)
            bands = self._discover_bands(product, metadata)
            self._validate_required_bands(bands)
            self._set_processing_state(scene, SentinelRasterStatus.PROCESSING, started_at=started_at)
            analysis = self._process(scene, region.id, product, metadata, bands, started_at)
            self._set_processing_state(scene, SentinelRasterStatus.READY, started_at=started_at, analysis=analysis)
            self.db.commit()
            return RasterProcessingResult(SentinelRasterStatus.READY, analysis.quality_status, analysis)
        except Exception as exc:
            self.db.rollback()
            if scene is not None:
                self._set_failure_state(scene, started_at, str(exc))
            return self._failure(SentinelRasterStatus.FAILED, str(exc), classify_provider_error(exc))

    def processing_status(self, region_id: str, scene_id: str | None = None) -> dict[str, Any]:
        try:
            region = get_region_location(region_id)
            scene = self._locate_scene(region.database_id, scene_id)
            if not scene:
                return self._status_payload(region.id, SentinelRasterStatus.UNAVAILABLE, "No acquired Sentinel-2 scene is available for this region.")
            metadata = scene.metadata_json or {}
            raster = metadata.get("raster_processing") or {}
            return {
                "region_id": region.id,
                "scene_id": scene.scene_id,
                "product_id": scene.product_id,
                "provider": scene.provider,
                "acquisition_status": scene.acquisition_status,
                "processing_status": raster.get("status", SentinelRasterStatus.DISCOVERED),
                "quality_status": scene.quality_status,
                "acquisition_time": scene.captured_at.isoformat() if scene.captured_at else None,
                "processing_time": scene.processing_time.isoformat() if scene.processing_time else None,
                "available_bands": raster.get("available_bands", []),
                "analysis_crs": raster.get("analysis_crs"),
                "resolution": raster.get("resolution"),
                "width": raster.get("width"),
                "height": raster.get("height"),
                "message": raster.get("message", "Raster preparation has not run for this scene."),
                "attribution": "Copernicus Data Space Ecosystem",
            }
        except ValueError as exc:
            raise
        except Exception as exc:
            return self._status_payload(region_id, SentinelRasterStatus.UNAVAILABLE, f"Raster processing status is unavailable: {exc.__class__.__name__}.")

    def _locate_scene(self, database_region_id: int, scene_id: str | None) -> SatelliteImage | None:
        if scene_id:
            return (
                self.db.query(SatelliteImage)
                .filter(
                    SatelliteImage.region_id == database_region_id,
                    SatelliteImage.provider == ProviderName.SENTINEL_2.value,
                    SatelliteImage.scene_id == scene_id,
                )
                .first()
            )
        return self.scenes.latest_sentinel_for_region(database_region_id)

    def _validate_scene(self, scene: SatelliteImage) -> None:
        if scene.provider != ProviderName.SENTINEL_2.value:
            raise ValueError("Scene provider is not Sentinel-2.")
        if scene.acquisition_status not in {SentinelAcquisitionStatus.ACQUIRED, SentinelAcquisitionStatus.VERIFIED}:
            raise ValueError("Sentinel scene has not been acquired.")
        if scene.product_level != "L2A":
            raise ValueError("Only Sentinel-2 Level-2A products are supported for raster preparation.")
        if not scene.product_id or not scene.scene_id:
            raise ValueError("Sentinel scene metadata is incomplete.")
        if not scene.storage_reference:
            raise FileNotFoundError("Sentinel scene storage reference is missing.")
        path = Path(scene.storage_reference)
        if not path.exists():
            raise FileNotFoundError("Sentinel scene file is missing.")

    def _open_product(self, path: Path) -> dict[str, Any]:
        if path.is_dir():
            return {"type": "directory", "root": path, "members": [member for member in path.rglob("*") if member.is_file()]}
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                members = [name for name in archive.namelist() if not name.endswith("/")]
                self._validate_zip_members(members)
            return {"type": "zip", "root": path, "members": members}
        raise ValueError("Unsupported Sentinel product storage format.")

    def _validate_zip_members(self, members: list[str]) -> None:
        for name in members:
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("Unsafe path found inside Sentinel product archive.")

    def _read_product_metadata(self, product: dict[str, Any]) -> dict[str, Any]:
        xml_text = self._read_first_text(product, r"(^|/)MTD_MSIL2A\.xml$")
        if xml_text is None:
            xml_text = self._read_first_text(product, r"(^|/)MTD_TL\.xml$")
        if xml_text is None:
            return {"quantification_value": 1.0, "offsets": {}, "scale_source": "metadata_missing_identity"}
        root = ElementTree.fromstring(xml_text)
        quantification = self._find_float(root, "BOA_QUANTIFICATION_VALUE") or self._find_float(root, "QUANTIFICATION_VALUE") or 1.0
        offsets = self._find_offsets(root)
        return {"quantification_value": quantification, "offsets": offsets, "scale_source": "product_metadata"}

    def _discover_bands(self, product: dict[str, Any], metadata: dict[str, Any]) -> dict[str, SpectralBand]:
        discovered: dict[str, SpectralBand] = {}
        for canonical, mapping in CANONICAL_BANDS.items():
            member = self._find_band_member(product, mapping["sentinel_id"])
            if member is None:
                continue
            dataset_path = self._dataset_path(product, member)
            try:
                with rasterio.open(dataset_path) as dataset:
                    discovered[canonical] = self._band_metadata(canonical, mapping["sentinel_id"], dataset_path, dataset, metadata)
            except RasterioIOError as exc:
                raise ValueError(f"Unable to read Sentinel band {mapping['sentinel_id']}: {exc}") from exc
        return discovered

    def _find_band_member(self, product: dict[str, Any], band_id: str) -> Any | None:
        pattern = re.compile(rf"(^|[_/]){re.escape(band_id)}(_(?:10|20|60)m)?\.(jp2|tif|tiff)$", re.IGNORECASE)
        members = product["members"]
        matches = [member for member in members if pattern.search(str(member))]
        if not matches:
            return None
        preferred_resolution = CANONICAL_BANDS[next(name for name, mapping in CANONICAL_BANDS.items() if mapping["sentinel_id"] == band_id)]["native_resolution_m"]
        preferred = [member for member in matches if f"_{preferred_resolution}m" in str(member)]
        return sorted(preferred or matches, key=lambda item: str(item))[0]

    def _dataset_path(self, product: dict[str, Any], member: Any) -> str:
        if product["type"] == "zip":
            return f"/vsizip/{product['root']}/{member}"
        return str(member)

    def _band_metadata(self, canonical: str, band_id: str, dataset_path: str, dataset: DatasetReader, metadata: dict[str, Any]) -> SpectralBand:
        if not dataset.crs:
            raise ValueError(f"Sentinel band {band_id} is missing CRS.")
        if dataset.width <= 0 or dataset.height <= 0:
            raise ValueError(f"Sentinel band {band_id} has invalid dimensions.")
        scale = RasterScale(
            quantification_value=float(metadata["quantification_value"]),
            offset=float(metadata.get("offsets", {}).get(band_id, 0.0)),
            source=metadata["scale_source"],
        )
        transform = dataset.transform
        return SpectralBand(
            name=canonical,
            source_identifier=band_id,
            path_reference=dataset_path,
            native_resolution=(abs(transform.a), abs(transform.e)),
            crs=dataset.crs.to_string(),
            transform=(transform.a, transform.b, transform.c, transform.d, transform.e, transform.f),
            width=dataset.width,
            height=dataset.height,
            bounds=tuple(dataset.bounds),
            dtype=dataset.dtypes[0],
            nodata=dataset.nodata,
            scale=scale,
        )

    def _validate_required_bands(self, bands: dict[str, SpectralBand]) -> None:
        missing = sorted(set(CANONICAL_BANDS) - set(bands))
        if missing:
            raise ValueError(f"Missing required Sentinel-2 bands: {', '.join(missing)}.")
        crs_values = {band.crs for band in bands.values()}
        if len(crs_values) != 1:
            raise ValueError("Required Sentinel bands do not share a CRS.")

    def _process(
        self,
        scene: SatelliteImage,
        region_id: str,
        product: dict[str, Any],
        metadata: dict[str, Any],
        bands: dict[str, SpectralBand],
        started_at: datetime,
    ) -> AnalysisReadyBands:
        reference_band = bands["SWIR"]
        with rasterio.open(reference_band.path_reference) as reference_dataset:
            window = self._analysis_window(reference_dataset, region_id)
            transform = reference_dataset.window_transform(window)
            width = int(window.width)
            height = int(window.height)
            if width <= 0 or height <= 0:
                raise ValueError("Requested region does not overlap the Sentinel scene.")
            self._validate_memory(width, height)
            bounds = tuple(rasterio.windows.bounds(window, reference_dataset.transform))
            analysis_crs = reference_dataset.crs
            analysis_transform = transform
            analysis_resolution = (abs(transform.a), abs(transform.e))

        output_dir = self._output_dir(scene, region_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_references: dict[str, str] = {}
        valid_masks: list[np.ndarray] = []
        profile = {
            "driver": "GTiff",
            "height": height,
            "width": width,
            "count": 1,
            "dtype": "float32",
            "crs": analysis_crs,
            "transform": analysis_transform,
            "nodata": PROCESSING_OUTPUT_NODATA,
            "compress": "deflate",
        }
        for canonical, band in bands.items():
            data, valid = self._read_analysis_band(band, analysis_crs, analysis_transform, width, height)
            output_path = output_dir / f"{canonical.lower()}.tif"
            with rasterio.open(output_path, "w", **profile) as destination:
                destination.write(data, 1)
            output_references[canonical] = str(output_path)
            valid_masks.append(valid)

        valid_mask = np.logical_and.reduce(valid_masks).astype("uint8")
        valid_mask_reference = output_dir / "valid_mask.tif"
        with rasterio.open(valid_mask_reference, "w", **{**profile, "dtype": "uint8", "nodata": 0}) as destination:
            destination.write(valid_mask, 1)

        completed_at = datetime.now(timezone.utc)
        provenance = {
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": PROCESSING_SOURCE_TYPE,
            "scene_id": scene.scene_id,
            "product_id": scene.product_id,
            "region_id": region_id,
            "acquisition_time": self._aware(scene.captured_at).isoformat() if scene.captured_at else None,
            "retrieved_at": self._aware(scene.retrieved_at).isoformat() if scene.retrieved_at else None,
            "processing_started_at": started_at.isoformat(),
            "processing_completed_at": completed_at.isoformat(),
            "source_band_identifiers": {name: band.source_identifier for name, band in bands.items()},
            "native_resolutions": {name: band.native_resolution for name, band in bands.items()},
            "analysis_resolution": analysis_resolution,
            "analysis_crs": analysis_crs.to_string(),
            "resampling_method": "bilinear_for_continuous_reflectance",
            "crop_bounds": bounds,
            "scale_offset_handling": {name: band.scale.to_dict() for name, band in bands.items()},
            "nodata": PROCESSING_OUTPUT_NODATA,
            "valid_mask": "nodata_and_finite_reflectance_only",
            "cloud_shadow_masking": "not_implemented_in_part_6d_1",
            "source_paths": {name: band.path_reference for name, band in bands.items()},
            "output_references": output_references,
        }
        analysis = AnalysisReadyBands(
            region_id=region_id,
            scene_id=scene.scene_id or "",
            product_id=scene.product_id or "",
            acquisition_time=self._aware(scene.captured_at) or completed_at,
            retrieved_at=self._aware(scene.retrieved_at),
            processing_started_at=started_at,
            processing_completed_at=completed_at,
            processing_status=SentinelRasterStatus.READY,
            quality_status=DataQualityStatus(scene.quality_status),
            analysis_crs=analysis_crs.to_string(),
            resolution=analysis_resolution,
            bounds=bounds,
            width=width,
            height=height,
            transform=(analysis_transform.a, analysis_transform.b, analysis_transform.c, analysis_transform.d, analysis_transform.e, analysis_transform.f),
            bands=bands,
            output_references=output_references,
            valid_mask_reference=str(valid_mask_reference),
            valid_pixel_count=int(valid_mask.sum()),
            total_pixel_count=int(valid_mask.size),
            provenance=provenance,
        )
        manifest_path = output_dir / "analysis_ready_manifest.json"
        manifest_payload = analysis.to_dict(expose_paths=True)
        manifest_payload["part"] = "6D-1 TEST/PROCESSING CONTRACT - NDVI and NBR not implemented"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, default=str))
        analysis.provenance["manifest_path"] = str(manifest_path)
        return analysis

    def _analysis_window(self, dataset: DatasetReader, region_id: str) -> Window:
        region = get_region_location(region_id)
        west, south, east, north = region.bounding_box()
        left, bottom, right, top = transform_bounds("EPSG:4326", dataset.crs, west, south, east, north, densify_pts=21)
        requested = from_bounds(left, bottom, right, top, dataset.transform)
        full = Window(0, 0, dataset.width, dataset.height)
        return requested.round_offsets().round_lengths().intersection(full)

    def _read_analysis_band(
        self,
        band: SpectralBand,
        analysis_crs,
        analysis_transform: Affine,
        width: int,
        height: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        with rasterio.open(band.path_reference) as source:
            vrt_options = {
                "crs": analysis_crs,
                "transform": analysis_transform,
                "width": width,
                "height": height,
                "resampling": Resampling.bilinear,
                "src_nodata": source.nodata,
                "dst_nodata": PROCESSING_OUTPUT_NODATA,
            }
            with WarpedVRT(source, **vrt_options) as vrt:
                raw = vrt.read(1, out_shape=(height, width), masked=True)
        data = raw.astype("float32").filled(PROCESSING_OUTPUT_NODATA)
        nodata_mask = np.ma.getmaskarray(raw)
        if band.nodata is not None:
            nodata_mask = nodata_mask | (data == float(band.nodata))
        data = np.where(nodata_mask, PROCESSING_OUTPUT_NODATA, data)
        valid = (~nodata_mask) & np.isfinite(data)
        reflectance = np.full(data.shape, PROCESSING_OUTPUT_NODATA, dtype="float32")
        reflectance[valid] = (data[valid] + band.scale.offset) / band.scale.quantification_value
        reflectance_valid = valid & np.isfinite(reflectance) & (reflectance > -1.0) & (reflectance < 3.0)
        reflectance = np.where(reflectance_valid, reflectance, PROCESSING_OUTPUT_NODATA).astype("float32")
        return reflectance, reflectance_valid

    def _validate_memory(self, width: int, height: int) -> None:
        estimated_bytes = width * height * (len(CANONICAL_BANDS) + 1) * 4
        max_bytes = int(self.settings.sentinel_raster_max_memory_mb * 1024 * 1024)
        if estimated_bytes > max_bytes:
            raise MemoryError("Requested Sentinel raster crop exceeds SENTINEL_RASTER_MAX_MEMORY_MB.")

    def _cached_result(self, scene: SatelliteImage, region_id: str) -> AnalysisReadyBands | None:
        raster = (scene.metadata_json or {}).get("raster_processing") or {}
        if raster.get("status") != SentinelRasterStatus.READY:
            return None
        manifest_path = raster.get("manifest_path")
        if not manifest_path or not Path(manifest_path).exists():
            return None
        payload = json.loads(Path(manifest_path).read_text())
        output_refs = payload.get("output_references") or payload.get("outputs") or {}
        if not all(Path(path).exists() for path in output_refs.values()):
            return None
        bands = self._bands_from_manifest(payload.get("bands", {}))
        return AnalysisReadyBands(
            region_id=region_id,
            scene_id=payload["scene_id"],
            product_id=payload["product_id"],
            acquisition_time=datetime.fromisoformat(payload["acquisition_time"]),
            retrieved_at=datetime.fromisoformat(payload["retrieved_at"]) if payload.get("retrieved_at") else None,
            processing_started_at=datetime.fromisoformat(payload["processing_started_at"]),
            processing_completed_at=datetime.fromisoformat(payload["processing_completed_at"]),
            processing_status=SentinelRasterStatus.READY,
            quality_status=DataQualityStatus(payload["quality_status"]),
            analysis_crs=payload["analysis_crs"],
            resolution=tuple(payload["resolution"]),
            bounds=tuple(payload["bounds"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            transform=tuple(payload["transform"]),
            bands=bands,
            output_references=output_refs,
            valid_mask_reference=str(self._output_dir(scene, region_id) / "valid_mask.tif"),
            valid_pixel_count=int(payload["valid_pixel_count"]),
            total_pixel_count=int(payload["total_pixel_count"]),
            provenance=payload.get("provenance", {}),
        )

    def _bands_from_manifest(self, payload: dict[str, Any]) -> dict[str, SpectralBand]:
        bands: dict[str, SpectralBand] = {}
        for name, item in payload.items():
            bands[name] = SpectralBand(
                name=item["name"],
                source_identifier=item["source_identifier"],
                path_reference="cached",
                native_resolution=tuple(item["native_resolution"]),
                crs=item["crs"],
                transform=tuple(item["transform"]),
                width=int(item["width"]),
                height=int(item["height"]),
                bounds=tuple(item["bounds"]),
                dtype=item["dtype"],
                nodata=item.get("nodata"),
                scale=RasterScale(**item["scale"]),
            )
        return bands

    def _set_processing_state(
        self,
        scene: SatelliteImage,
        status: str,
        started_at: datetime | None = None,
        analysis: AnalysisReadyBands | None = None,
        message: str | None = None,
    ) -> None:
        metadata = dict(scene.metadata_json or {})
        raster = dict(metadata.get("raster_processing") or {})
        raster.update(
            {
                "status": status,
                "message": message or ("Raster preparation complete." if status == SentinelRasterStatus.READY else "Raster preparation in progress."),
                "started_at": started_at.isoformat() if started_at else raster.get("started_at"),
            }
        )
        if analysis:
            raster.update(
                {
                    "available_bands": sorted(analysis.bands),
                    "analysis_crs": analysis.analysis_crs,
                    "resolution": analysis.resolution,
                    "width": analysis.width,
                    "height": analysis.height,
                    "manifest_path": analysis.provenance.get("manifest_path"),
                    "completed_at": analysis.processing_completed_at.isoformat(),
                }
            )
            scene.processing_time = analysis.processing_completed_at.replace(tzinfo=None)
        metadata["raster_processing"] = raster
        scene.metadata_json = metadata
        self.db.flush()

    def _set_failure_state(self, scene: SatelliteImage, started_at: datetime, message: str) -> None:
        try:
            metadata = dict(scene.metadata_json or {})
            metadata["raster_processing"] = {
                **dict(metadata.get("raster_processing") or {}),
                "status": SentinelRasterStatus.FAILED,
                "message": message,
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            scene.metadata_json = metadata
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _failure(self, status: str, message: str, kind: ProviderErrorKind) -> RasterProcessingResult:
        return RasterProcessingResult(status, DataQualityStatus.UNAVAILABLE, None, RasterProcessingError(kind, message))

    def _status_payload(self, region_id: str, status: str, message: str) -> dict[str, Any]:
        return {
            "region_id": region_id,
            "scene_id": None,
            "product_id": None,
            "provider": ProviderName.SENTINEL_2.value,
            "acquisition_status": SentinelAcquisitionStatus.UNAVAILABLE,
            "processing_status": status,
            "quality_status": DataQualityStatus.UNAVAILABLE.value,
            "acquisition_time": None,
            "processing_time": None,
            "available_bands": [],
            "analysis_crs": None,
            "resolution": None,
            "width": None,
            "height": None,
            "message": message,
            "attribution": "Copernicus Data Space Ecosystem",
        }

    def _output_dir(self, scene: SatelliteImage, region_id: str) -> Path:
        safe_scene = re.sub(r"[^A-Za-z0-9_.-]+", "_", scene.product_id or scene.scene_id or "scene")
        safe_region = re.sub(r"[^A-Za-z0-9_.-]+", "_", region_id)
        return Path(self.settings.sentinel_processing_dir) / safe_scene / safe_region

    def _read_first_text(self, product: dict[str, Any], pattern: str) -> str | None:
        matcher = re.compile(pattern, re.IGNORECASE)
        for member in product["members"]:
            member_text = str(member)
            if not matcher.search(member_text):
                continue
            if product["type"] == "zip":
                with zipfile.ZipFile(product["root"]) as archive:
                    return archive.read(member_text).decode("utf-8")
            return Path(member).read_text()
        return None

    def _find_float(self, root: ElementTree.Element, local_name: str) -> float | None:
        for item in root.iter():
            if item.tag.split("}")[-1] == local_name and item.text:
                try:
                    return float(item.text)
                except ValueError:
                    return None
        return None

    def _find_offsets(self, root: ElementTree.Element) -> dict[str, float]:
        band_id_map = {
            "0": "B01",
            "1": "B02",
            "2": "B03",
            "3": "B04",
            "4": "B05",
            "5": "B06",
            "6": "B07",
            "7": "B08",
            "8": "B8A",
            "9": "B09",
            "10": "B10",
            "11": "B11",
            "12": "B12",
        }
        offsets: dict[str, float] = {}
        for item in root.iter():
            if item.tag.split("}")[-1] != "BOA_ADD_OFFSET" or not item.text:
                continue
            identifier = item.attrib.get("band_id") or item.attrib.get("physicalBand") or item.attrib.get("band")
            band = band_id_map.get(str(identifier), str(identifier) if identifier else "")
            if not band.startswith("B"):
                continue
            offsets[band] = float(item.text)
        return offsets

    def _aware(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
