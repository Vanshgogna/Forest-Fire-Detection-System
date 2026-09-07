from backend.services.remote_sensing import RasterScene, RemoteSensingPipeline
from backend.services.satellite_processor import SatelliteProcessor


def test_scene_validation_rejects_unsupported_source_and_cloud_over_threshold():
    pipeline = RemoteSensingPipeline()
    scene = RasterScene(scene_id="S2A_TEST", source="Unknown", acquisition_date="2026-08-02", cloud_percentage=90)

    validation = pipeline.validate_scene(scene)

    assert validation["valid"] is False
    assert len(validation["errors"]) == 2


def test_invalid_scene_download_manifest_is_blocked():
    pipeline = RemoteSensingPipeline()
    scene = RasterScene(scene_id="bad", source="Unknown", acquisition_date="2026-08-02")

    manifest = pipeline.satellite_download_manifest(scene)

    assert manifest["status"] == "blocked"
    assert manifest["required_bands"] == []


def test_processing_plan_uses_windowed_large_raster_strategy():
    pipeline = RemoteSensingPipeline()
    scene = RasterScene(scene_id="S2A_TEST", source="Sentinel-2", acquisition_date="2026-08-02", cloud_percentage=12)

    plan = pipeline.raster_processing_plan(scene)

    assert plan["valid"] is True
    assert plan["processing_mode"] == "windowed"
    assert plan["chunk_size"] == 1024
    assert "calculate_ndvi" in plan["steps"]
    assert "calculate_nbr" in plan["steps"]


def test_satellite_processor_full_scene_plan_includes_storage_and_cleanup():
    processor = SatelliteProcessor()
    plan = processor.full_scene_plan(
        {
            "scene_id": "S2A_TILE_001",
            "source": "Sentinel-2",
            "acquisition_date": "2026-08-02",
            "cloud_percentage": 20,
        }
    )

    assert plan["validation"]["valid"] is True
    assert "storage" in plan
    assert plan["cleanup"]["safe_to_delete"] is True


def test_heatmap_feature_clamps_weight():
    pipeline = RemoteSensingPipeline()
    feature = pipeline.heatmap_feature(longitude=77.1, latitude=12.9, weight=2.4)

    assert feature["properties"]["weight"] == 1.0


def test_scalar_indices_use_shared_normalized_difference_formula():
    processor = SatelliteProcessor()

    assert processor.calculate_ndvi(0.8, 0.2) == processor.pipeline.normalized_difference(0.8, 0.2)
    assert processor.calculate_nbr(0.8, 0.4) == processor.pipeline.normalized_difference(0.8, 0.4)


def test_cleanup_plan_uses_sanitized_scene_id_for_paths():
    pipeline = RemoteSensingPipeline()
    plan = pipeline.cleanup_plan("../unsafe scene")

    assert ".." not in plan["target"]
    assert "unsafe_scene" in plan["target"]
    assert plan["safe_to_delete"] is True
