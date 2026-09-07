from __future__ import annotations

from backend.services.remote_sensing import DEFAULT_ANALYSIS_CRS, DEFAULT_CHUNK_SIZE, DEFAULT_PROJECT_CRS, DEFAULT_TILE_ZOOMS, RasterScene, RemoteSensingPipeline


class SatelliteProcessor:
    def __init__(self):
        self.pipeline = RemoteSensingPipeline()

    def calculate_ndvi(self, nir: float, red: float) -> float:
        return self.pipeline.normalized_difference(nir, red)

    def calculate_nbr(self, nir: float, swir: float) -> float:
        return self.pipeline.normalized_difference(nir, swir)

    def vegetation_health_index(self, ndvi: float, nbr: float, cloud_percentage: float = 0) -> float:
        cloud_penalty = min(0.25, cloud_percentage / 400)
        return round(max(0, min(1, (ndvi * 0.65 + nbr * 0.35) - cloud_penalty)), 4)

    def metadata_summary(self, source: str = "Sentinel-2") -> dict:
        return {"source": source, "status": "processed", "cloud_mask": "applied", "tiling": "ready"}

    def calculate_index_array(self, band_a, band_b):
        return self.pipeline.calculate_index_array(band_a, band_b)

    def preprocessing_plan(self, source: str = "Sentinel-2") -> dict:
        scene = RasterScene(scene_id="scene-preview", source=source, acquisition_date="not-specified")
        return {
            "source": source,
            "dataset_validation": self.pipeline.validate_scene(scene),
            "coordinate_systems": {"project_crs": DEFAULT_PROJECT_CRS, "analysis_crs": DEFAULT_ANALYSIS_CRS},
            "projection_conversion": self.pipeline.projection_plan(scene.crs),
            "steps": [
                "validate_scene_metadata",
                "apply_cloud_mask",
                "reproject_to_project_crs",
                "clip_to_forest_boundary",
                "calculate_ndvi",
                "calculate_nbr",
                "tile_for_map_services",
                "persist_metadata",
            ],
            "outputs": ["ndvi", "nbr", "vegetation_health_index", "cloud_mask", "map_tiles", "metadata_json"],
            "performance": {"processing_mode": "windowed", "chunk_size": DEFAULT_CHUNK_SIZE},
        }

    def tile_manifest(self, scene_id: str, zoom_levels: list[int] | None = None) -> dict:
        manifest = self.pipeline.tile_cache_manifest(scene_id=scene_id, layer="vegetation", zoom_levels=zoom_levels or DEFAULT_TILE_ZOOMS)
        return {**manifest, "status": "ready_for_worker"}

    def full_scene_plan(self, payload: dict) -> dict:
        scene = RasterScene(
            scene_id=payload["scene_id"],
            source=payload.get("source", "Sentinel-2"),
            acquisition_date=payload.get("acquisition_date", "not-specified"),
            crs=payload.get("crs", "EPSG:4326"),
            cloud_percentage=float(payload.get("cloud_percentage", 0)),
            storage_uri=payload.get("storage_uri"),
            bounds=payload.get("bounds"),
        )
        outputs = ["ndvi", "nbr", "vegetation_health", "cloud_mask", "tiles"]
        return {
            "download": self.pipeline.satellite_download_manifest(scene),
            "validation": self.pipeline.validate_scene(scene),
            "projection": self.pipeline.projection_plan(scene.crs),
            "cloud_mask": self.pipeline.cloud_mask_plan(scene),
            "processing": self.pipeline.raster_processing_plan(scene),
            "storage": self.pipeline.storage_manifest(scene, outputs),
            "temporary_files": self.pipeline.temporary_file_manifest(scene.scene_id, ["download", "reproject", "clip", "indices"]),
            "cleanup": self.pipeline.cleanup_plan(scene.scene_id),
        }
