from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.security import create_access_token
from backend.data.automation import PipelineAutomationPlanner
from backend.data.pipeline import DataPipeline, PipelineManifest
from backend.data.sources import DataIngestionClient, DataSource, RefreshMode, RefreshPolicy, SourceKind
from backend.data.validation import DataValidator
from backend.main import app


def _pipeline(root: Path) -> DataPipeline:
    return DataPipeline(
        dataset_root=root / "datasets",
        cache_root=root / "cache",
        archive_root=root / "archive",
        checkpoint_root=root / "checkpoints",
    )


def _csv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_csv_pipeline_extracts_validates_profiles_archives_and_versions_dataset(tmp_path):
    source_file = _csv(
        tmp_path / "fire_history.csv",
        "latitude,longitude,temperature,humidity,risk_class\n"
        "11.1,76.9,36,28,High\n"
        "11.2,77.0,32,44,Moderate\n"
        "11.2,77.0,32,44,Moderate\n",
    )
    manifest = PipelineManifest(
        dataset_id="fire-history",
        dataset_version="2026-08-23",
        source=DataSource(name="Historical fires", kind=SourceKind.HISTORICAL_FIRE, uri=str(source_file)),
        storage_format="csv",
        required_fields=["latitude", "longitude", "temperature", "humidity", "risk_class"],
        coordinate_fields=("latitude", "longitude"),
        label_field="risk_class",
        baseline_statistics={"temperature": {"mean": 25.0}},
    )

    result = _pipeline(tmp_path).run(manifest)

    assert result.status == "completed"
    assert result.validation.valid is True
    assert result.validation.record_count == 3
    assert result.quality is not None
    assert result.quality.duplicate_records == 1
    assert result.quality.class_distribution == {"High": 1, "Moderate": 2}
    assert result.quality.drift["temperature"] >= 0.2
    assert result.dataset_version is not None
    assert result.dataset_version.processing_version == "etl-2026.08"
    assert Path(result.archive_path or "").exists()
    assert Path(result.version_manifest_path or "").exists()
    assert json.loads(Path(result.checkpoint_path).read_text(encoding="utf-8"))["status"] == "completed"


def test_pipeline_stops_before_storage_when_validation_fails(tmp_path):
    source_file = _csv(tmp_path / "bad_weather.csv", "latitude,longitude,temperature\n95,200,44\n")
    manifest = PipelineManifest(
        dataset_id="weather-invalid",
        dataset_version="v1",
        source=DataSource(name="Weather sample", kind=SourceKind.WEATHER_API, uri=str(source_file)),
        storage_format="csv",
        required_fields=["latitude", "longitude", "humidity"],
        coordinate_fields=("latitude", "longitude"),
    )

    result = _pipeline(tmp_path).run(manifest)

    assert result.status == "failed_validation"
    assert result.validation.valid is False
    assert any("missing required fields" in error for error in result.validation.errors)
    assert any("coordinate out of range" in error for error in result.validation.errors)
    assert result.archive_path is None
    assert result.version_manifest_path is None
    checkpoint = json.loads(Path(result.checkpoint_path).read_text(encoding="utf-8"))
    assert checkpoint["resumable"] is True
    assert checkpoint["next_stage"] == "normalize"


def test_weather_csv_pipeline_requires_weather_fields(tmp_path):
    source_file = _csv(tmp_path / "weather.csv", "latitude,longitude,temperature,humidity,wind_speed\n11.1,76.9,36,101,4\n")
    manifest = PipelineManifest(
        dataset_id="weather-feed",
        dataset_version="2026-08-24",
        source=DataSource(name="Weather API", kind=SourceKind.WEATHER_API, uri=str(source_file)),
        storage_format="csv",
        required_fields=["latitude", "longitude", "temperature", "humidity", "wind_speed"],
        coordinate_fields=("latitude", "longitude"),
    )

    result = _pipeline(tmp_path).run(manifest)

    assert result.status == "failed_validation"
    assert any("missing weather fields: rainfall" in error for error in result.validation.errors)
    assert any("humidity must be between 0 and 100" in error for error in result.validation.errors)


def test_ingestion_skips_incremental_download_when_checksum_matches(tmp_path):
    source_file = _csv(tmp_path / "source.csv", "id,value\n1,10\n")
    checksum = sha256(source_file.read_bytes()).hexdigest()
    destination = tmp_path / "downloads" / "source.csv"
    client = DataIngestionClient()

    first = client.ingest(DataSource(name="CSV", kind=SourceKind.CSV, uri=str(source_file), expected_checksum=checksum), destination)
    second = client.ingest(DataSource(name="CSV", kind=SourceKind.CSV, uri=str(source_file), expected_checksum=checksum), destination)

    assert first.skipped is False
    assert first.progress_bytes[-1] == source_file.stat().st_size
    assert second.skipped is True
    assert second.checksum == checksum
    assert second.progress_bytes == [source_file.stat().st_size]


def test_validator_detects_corrupted_geojson_and_missing_shapefile_sidecars(tmp_path):
    validator = DataValidator()
    bad_geojson = tmp_path / "bad.geojson"
    bad_geojson.write_text("{not-json", encoding="utf-8")
    shp = tmp_path / "forest.shp"
    shp.write_text("shape", encoding="utf-8")

    geojson_result = validator.validate_geojson(bad_geojson)
    shapefile_result = validator.validate_shapefile(shp)

    assert geojson_result.valid is False
    assert "geojson file is malformed" in geojson_result.errors
    assert shapefile_result.valid is False
    assert "missing shapefile sidecars" in shapefile_result.errors[0]


def test_validator_detects_corrupted_raster_and_invalid_crs(tmp_path):
    validator = DataValidator()
    raster = tmp_path / "scene.tif"
    raster.write_bytes(b"bad")

    result = validator.validate_raster(raster, expected_crs="WGS84")

    assert result.valid is False
    assert "raster file is truncated or corrupted" in result.errors
    assert "raster CRS is invalid" in result.errors


def test_automation_planner_documents_incremental_refresh_plan(tmp_path):
    source_file = _csv(tmp_path / "modis.csv", "id,acquired_at\n1,2026-08-24T00:00:00Z\n")
    manifest = PipelineManifest(
        dataset_id="modis-hotspots",
        dataset_version="2026-08-24",
        source=DataSource(
            name="MODIS",
            kind=SourceKind.MODIS,
            uri=str(source_file),
            refresh_policy=RefreshPolicy(
                mode=RefreshMode.INCREMENTAL,
                incremental_field="acquired_at",
                last_watermark="2026-08-23T00:00:00Z",
            ),
        ),
        storage_format="csv",
    )

    planner = PipelineAutomationPlanner()
    plan = planner.plan(manifest)

    assert plan.to_dict()["refresh_mode"] == "incremental"
    assert plan.task_name == "firesight.run_data_pipeline"
    assert planner.should_process_increment(manifest, "2026-08-24T00:00:00Z") is True
    assert planner.should_process_increment(manifest, "2026-08-22T00:00:00Z") is False


def test_data_sources_api_is_role_protected_and_documents_pipeline_sources():
    token = create_access_token("researcher@example.com", {"role": "researcher"})
    client = TestClient(app)

    response = client.get("/api/data/sources", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert "Sentinel-2" in payload["supported_sources"]
    assert "extract" in payload["pipeline_stages"]
    assert "version" in payload["pipeline_stages"]
    assert "incremental" in payload["refresh_modes"]
