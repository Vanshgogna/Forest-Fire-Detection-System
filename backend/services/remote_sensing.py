"""Reusable GIS and remote-sensing operation contracts.

The API uses this module to describe satellite processing work, while Celery
workers can later execute the same manifests with Rasterio/GDAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import logging
from pathlib import Path
from tempfile import gettempdir
import time
import re

try:
    import numpy as np
except Exception:  # pragma: no cover - optional scientific dependency
    np = None

SUPPORTED_SATELLITE_SOURCES = {"Sentinel-2", "MODIS", "VIIRS"}
DEFAULT_PROJECT_CRS = "EPSG:4326"
DEFAULT_ANALYSIS_CRS = "EPSG:3857"
DEFAULT_TILE_ZOOMS = [8, 9, 10, 11, 12]
MAX_CLOUD_PERCENTAGE = 80.0
DEFAULT_CHUNK_SIZE = 1024

logger = logging.getLogger("firesight.remote_sensing")


@dataclass(frozen=True)
class RasterScene:
    """Metadata required to validate and process one satellite scene."""

    scene_id: str
    source: str
    acquisition_date: str
    crs: str = DEFAULT_PROJECT_CRS
    cloud_percentage: float = 0.0
    storage_uri: str | None = None
    bounds: dict | None = None


class RemoteSensingPipeline:
    """Build reusable manifests and array operations for remote-sensing workflows."""

    def __init__(self, storage_root: str = "backend/artifacts/rasters", temp_root: str | None = None):
        self.storage_root = Path(storage_root)
        self.temp_root = Path(temp_root or gettempdir()) / "firesight-remote-sensing"

    def satellite_download_manifest(self, scene: RasterScene) -> dict:
        """Return the source bands, destination, validation status, and cache key for scene acquisition."""
        validation = self.validate_scene(scene)
        safe_scene_id = self.safe_scene_id(scene.scene_id)
        logger.info(
            "satellite_download_manifest source=%s valid=%s required_bands=%s",
            scene.source,
            validation["valid"],
            len(self.required_bands(scene.source)),
        )
        return {
            "scene_id": scene.scene_id,
            "source": scene.source,
            "status": "ready_for_download" if validation["valid"] else "blocked",
            "validation": validation,
            "storage_uri": scene.storage_uri or str(self.storage_root / scene.source.lower().replace("-", "_") / safe_scene_id),
            "required_bands": self.required_bands(scene.source),
            "cache_key": self.cache_key("download", scene.scene_id, scene.source),
        }

    def validate_scene(self, scene: RasterScene) -> dict:
        """Validate scene identity, supported source, and cloud coverage constraints."""
        errors = []
        if not scene.scene_id.strip():
            errors.append("scene_id is required")
        if scene.source not in SUPPORTED_SATELLITE_SOURCES:
            errors.append(f"unsupported source: {scene.source}")
        if not 0 <= scene.cloud_percentage <= 100:
            errors.append("cloud_percentage must be between 0 and 100")
        if scene.cloud_percentage > MAX_CLOUD_PERCENTAGE:
            errors.append("cloud coverage exceeds processing threshold")
        if errors:
            logger.warning("satellite_scene_validation_failed source=%s error_count=%s", scene.source, len(errors))
            return {"valid": False, "errors": errors}
        logger.info("satellite_scene_validation_passed source=%s cloud_percentage=%.2f", scene.source, scene.cloud_percentage)
        return {"valid": True, "errors": []}

    def required_bands(self, source: str) -> list[str]:
        """Return source-specific bands required for the configured processing workflow."""
        if source == "Sentinel-2":
            return ["B04_RED", "B08_NIR", "B12_SWIR", "SCL_CLOUD_MASK"]
        if source == "MODIS":
            return ["thermal_anomaly", "confidence", "brightness_temperature"]
        if source == "VIIRS":
            return ["thermal_anomaly", "confidence", "frp"]
        return []

    def projection_plan(self, source_crs: str, target_crs: str = DEFAULT_ANALYSIS_CRS) -> dict:
        """Describe whether CRS conversion is required before analysis or web-map rendering."""
        return {
            "source_crs": source_crs,
            "target_crs": target_crs,
            "conversion_required": source_crs != target_crs,
            "resampling": "bilinear",
        }

    def raster_processing_plan(self, scene: RasterScene, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
        """Build a memory-safe, windowed processing plan for large satellite rasters."""
        started = time.perf_counter()
        validation = self.validate_scene(scene)
        logger.info(
            "raster_processing_plan_created source=%s valid=%s chunk_size=%s",
            scene.source,
            validation["valid"],
            chunk_size,
        )
        result = {
            "scene_id": scene.scene_id,
            "valid": validation["valid"],
            "errors": validation["errors"],
            "chunk_size": chunk_size,
            "processing_mode": "windowed",
            "steps": [
                "download_or_read_scene",
                "validate_dataset_metadata",
                "convert_projection",
                "apply_cloud_mask",
                "clip_to_forest_boundary",
                "calculate_ndvi",
                "calculate_nbr",
                "normalize_rasters",
                "write_cloud_optimized_outputs",
                "publish_tile_manifest",
            ],
            "cache_key": self.cache_key("processing", scene.scene_id, scene.source, scene.crs),
        }
        try:
            from backend.services.observability import observability_registry

            observability_registry.record_raster_processing(
                operation="raster_processing_plan",
                elapsed_ms=(time.perf_counter() - started) * 1000,
                status="ok" if validation["valid"] else "failed_validation",
            )
        except Exception:
            pass
        return result

    def clip_plan(self, scene: RasterScene, boundary_geojson: dict) -> dict:
        """Describe clipping a raster scene to a forest boundary geometry."""
        logger.info("gis_clip_plan_created source=%s boundary_type=%s", scene.source, boundary_geojson.get("type", "Unknown"))
        return {
            "scene_id": scene.scene_id,
            "boundary_type": boundary_geojson.get("type", "Unknown"),
            "operation": "clip_raster_by_geometry",
            "cache_key": self.cache_key("clip", scene.scene_id, str(boundary_geojson)),
        }

    def cloud_mask_plan(self, scene: RasterScene) -> dict:
        """Describe the source-specific cloud mask strategy for a scene."""
        processable = scene.cloud_percentage <= MAX_CLOUD_PERCENTAGE
        if not processable:
            logger.warning("cloud_mask_blocked source=%s cloud_percentage=%.2f", scene.source, scene.cloud_percentage)
        return {
            "scene_id": scene.scene_id,
            "source": scene.source,
            "mask_band": "SCL_CLOUD_MASK" if scene.source == "Sentinel-2" else "confidence",
            "max_cloud_percentage": MAX_CLOUD_PERCENTAGE,
            "cloud_percentage": scene.cloud_percentage,
            "processable": processable,
        }

    def calculate_index_array(self, band_a, band_b):
        """Calculate a normalized-difference raster array without loading unrelated bands."""
        if np is None:
            logger.error("raster_index_failed reason=missing_numpy")
            raise RuntimeError("NumPy is required for raster index calculation")
        band_a = np.asarray(band_a, dtype="float32")
        band_b = np.asarray(band_b, dtype="float32")
        denominator = band_a + band_b
        return np.divide(band_a - band_b, denominator, out=np.zeros_like(band_a), where=denominator != 0)

    def normalized_difference(self, band_a: float, band_b: float) -> float:
        """Calculate scalar normalized difference for NDVI/NBR-compatible indices."""
        denominator = band_a + band_b
        if denominator == 0:
            return 0.0
        return round((band_a - band_b) / denominator, 4)

    def normalize_array(self, raster, lower: float = -1.0, upper: float = 1.0):
        """Normalize raster values to a zero-to-one range after clipping to expected bounds."""
        if np is None:
            logger.error("raster_normalization_failed reason=missing_numpy")
            raise RuntimeError("NumPy is required for raster normalization")
        if upper == lower:
            logger.warning("raster_normalization_failed reason=invalid_bounds")
            raise ValueError("Normalization upper and lower bounds must be different")
        raster = np.asarray(raster, dtype="float32")
        clipped = np.clip(raster, lower, upper)
        return (clipped - lower) / (upper - lower)

    def geojson_feature_collection(self, features: list[dict]) -> dict:
        """Wrap prebuilt GeoJSON features in a FeatureCollection."""
        logger.info("geojson_feature_collection_created feature_count=%s", len(features))
        return {"type": "FeatureCollection", "features": features}

    def heatmap_feature(self, longitude: float, latitude: float, weight: float, properties: dict | None = None) -> dict:
        """Create a point feature with heatmap weight clamped to the renderer-safe range."""
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {"weight": max(0.0, min(1.0, weight)), **(properties or {})},
        }

    def tile_cache_manifest(self, scene_id: str, layer: str, zoom_levels: list[int] | None = None) -> dict:
        """Return deterministic tile cache metadata for a scene layer."""
        zoom_levels = zoom_levels or DEFAULT_TILE_ZOOMS
        logger.info("tile_cache_manifest_created layer=%s zoom_count=%s", layer, len(zoom_levels))
        return {
            "scene_id": scene_id,
            "layer": layer,
            "tile_scheme": "XYZ",
            "zoom_levels": zoom_levels,
            "cache_key": self.cache_key("tiles", scene_id, layer, ",".join(str(zoom) for zoom in zoom_levels)),
        }

    def storage_manifest(self, scene: RasterScene, outputs: list[str]) -> dict:
        """Return stable storage paths for generated raster products and metadata."""
        base_path = self.storage_root / scene.source.lower().replace("-", "_") / self.safe_scene_id(scene.scene_id)
        return {
            "scene_id": scene.scene_id,
            "storage_root": str(base_path),
            "outputs": {output: str(base_path / f"{output}.tif") for output in outputs},
            "metadata": str(base_path / "metadata.json"),
        }

    def temporary_file_manifest(self, scene_id: str, stages: list[str]) -> dict:
        """Return temporary files expected during worker execution for later cleanup."""
        safe_scene_id = self.safe_scene_id(scene_id)
        files = [str(self.temp_root / safe_scene_id / f"{stage}.tmp") for stage in stages]
        return {"scene_id": scene_id, "temp_root": str(self.temp_root / safe_scene_id), "files": files, "cleanup_required": True}

    def cleanup_plan(self, scene_id: str) -> dict:
        """Return a safe cleanup target for a scene's temporary workspace."""
        safe_scene_id = self.safe_scene_id(scene_id)
        return {
            "scene_id": scene_id,
            "operation": "remove_temporary_scene_workspace",
            "target": str(self.temp_root / safe_scene_id),
            "safe_to_delete": bool(safe_scene_id),
        }

    def cache_key(self, *parts: str) -> str:
        """Build a compact deterministic cache key for GIS and raster artifacts."""
        raw = ":".join(parts)
        return "rs:" + sha256(raw.encode("utf-8")).hexdigest()[:24]

    def safe_scene_id(self, scene_id: str) -> str:
        """Sanitize scene identifiers before using them in filesystem paths."""
        sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", scene_id.strip())
        return sanitized.strip("._-")
