from __future__ import annotations

from pathlib import Path

from backend.core.config import get_settings
from backend.database.session import SessionLocal
from backend.data.pipeline import DataPipeline, PipelineManifest
from backend.data.sources import DataSource, RefreshMode, RefreshPolicy, SourceKind
from backend.services.hotspot_ingestion_service import FIRMSIngestionService
from backend.services.sentinel_acquisition_service import SentinelAcquisitionService
from backend.services.sentinel_ndvi_service import SentinelNDVIService
from backend.services.sentinel_quality_mask_service import SentinelQualityMaskService
from backend.services.sentinel_raster_service import SentinelRasterService
from backend.tasks.celery_app import celery_app


def _run_data_pipeline_job(payload: dict) -> dict:
    settings = get_settings()
    source = payload["source"]
    pipeline = DataPipeline(
        dataset_root=Path(settings.dataset_dir),
        cache_root=Path(settings.cache_artifact_dir) / "data-pipeline",
        archive_root=Path(settings.data_archive_dir),
        checkpoint_root=Path(settings.data_checkpoint_dir),
    )
    manifest = PipelineManifest(
        dataset_id=payload["dataset_id"],
        dataset_version=payload["dataset_version"],
        source=DataSource(
            name=source["name"],
            kind=SourceKind(source["kind"]),
            uri=source["uri"],
            expected_checksum=source.get("expected_checksum"),
            version=source.get("version", "v1"),
            metadata=source.get("metadata", {}),
            refresh_policy=RefreshPolicy(
                mode=RefreshMode(source.get("refresh_mode", RefreshMode.MANUAL.value)),
                schedule_cron=source.get("schedule_cron"),
                incremental_field=source.get("incremental_field"),
                last_watermark=source.get("last_watermark"),
                checkpoint_enabled=source.get("checkpoint_enabled", True),
            ),
        ),
        storage_format=payload["storage_format"],
        required_fields=payload.get("required_fields", []),
        coordinate_fields=tuple(payload["coordinate_fields"]) if payload.get("coordinate_fields") else None,
        label_field=payload.get("label_field"),
        expected_crs=payload.get("expected_crs", "EPSG:4326"),
        baseline_statistics=payload.get("baseline_statistics", {}),
        model_version_compatibility=payload.get("model_version_compatibility", ["wildfire-risk-rf-v1", "wildfire-risk-xgb-v1"]),
    )
    return pipeline.run(manifest).to_dict()


def _ingest_firms_hotspots(region_ids: list[str] | None = None) -> dict:
    with SessionLocal() as db:
        return FIRMSIngestionService(db).ingest_regions(region_ids).to_dict()


def _acquire_latest_sentinel_scene(region_ids: list[str] | None = None) -> dict:
    with SessionLocal() as db:
        return SentinelAcquisitionService(db).acquire_latest_scene(region_ids).to_dict()


def _prepare_sentinel_raster(region_id: str, scene_id: str | None = None) -> dict:
    with SessionLocal() as db:
        return SentinelRasterService(db).prepare_analysis_ready_bands(region_id, scene_id).to_dict()


def _apply_sentinel_quality_mask(region_id: str, scene_id: str | None = None) -> dict:
    with SessionLocal() as db:
        return SentinelQualityMaskService(db).apply_quality_mask(region_id, scene_id).to_dict()


def _calculate_sentinel_ndvi(region_id: str, scene_id: str | None = None) -> dict:
    with SessionLocal() as db:
        return SentinelNDVIService(db).calculate_ndvi(region_id, scene_id).to_dict()


if celery_app:
    @celery_app.task(name="firesight.run_scheduled_prediction")
    def run_scheduled_prediction() -> dict:
        return {"status": "queued", "job": "scheduled_prediction"}

    @celery_app.task(name="firesight.process_satellite_scene")
    def process_satellite_scene(scene_id: str) -> dict:
        return {"status": "queued", "scene_id": scene_id}

    @celery_app.task(name="firesight.download_satellite_scene")
    def download_satellite_scene(scene: dict) -> dict:
        return {"status": "queued", "job": "satellite_download", "scene": scene}

    @celery_app.task(name="firesight.update_weather_records")
    def update_weather_records(region_ids: list[int] | None = None) -> dict:
        return {"status": "queued", "job": "weather_update", "region_ids": region_ids or "all"}

    @celery_app.task(name="firesight.generate_report")
    def generate_report(report_type: str, payload: dict) -> dict:
        return {"status": "queued", "job": "report_generation", "report_type": report_type, "payload": payload}

    @celery_app.task(name="firesight.deliver_notification")
    def deliver_notification(notification: dict) -> dict:
        return {"status": "queued", "job": "notification_delivery", "notification": notification}

    @celery_app.task(name="firesight.retrain_model")
    def retrain_model(algorithm: str = "random_forest") -> dict:
        return {"status": "queued", "job": "model_retraining", "algorithm": algorithm}

    @celery_app.task(name="firesight.run_data_pipeline")
    def run_data_pipeline(payload: dict) -> dict:
        return _run_data_pipeline_job(payload)

    @celery_app.task(name="firesight.ingest_firms_hotspots", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
    def ingest_firms_hotspots(region_ids: list[str] | None = None) -> dict:
        return _ingest_firms_hotspots(region_ids)

    @celery_app.task(name="firesight.acquire_latest_sentinel_scene", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
    def acquire_latest_sentinel_scene(region_ids: list[str] | None = None) -> dict:
        return _acquire_latest_sentinel_scene(region_ids)

    @celery_app.task(name="firesight.prepare_sentinel_raster", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 1})
    def prepare_sentinel_raster(region_id: str, scene_id: str | None = None) -> dict:
        return _prepare_sentinel_raster(region_id, scene_id)

    @celery_app.task(name="firesight.apply_sentinel_quality_mask", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 1})
    def apply_sentinel_quality_mask(region_id: str, scene_id: str | None = None) -> dict:
        return _apply_sentinel_quality_mask(region_id, scene_id)

    @celery_app.task(name="firesight.calculate_sentinel_ndvi", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 1})
    def calculate_sentinel_ndvi(region_id: str, scene_id: str | None = None) -> dict:
        return _calculate_sentinel_ndvi(region_id, scene_id)
else:
    def run_scheduled_prediction() -> dict:
        return {"status": "disabled", "reason": "Celery is not installed"}

    def process_satellite_scene(scene_id: str) -> dict:
        return {"status": "disabled", "scene_id": scene_id}

    def download_satellite_scene(scene: dict) -> dict:
        return {"status": "disabled", "scene": scene}

    def update_weather_records(region_ids: list[int] | None = None) -> dict:
        return {"status": "disabled", "region_ids": region_ids or "all"}

    def generate_report(report_type: str, payload: dict) -> dict:
        return {"status": "disabled", "report_type": report_type, "payload": payload}

    def deliver_notification(notification: dict) -> dict:
        return {"status": "disabled", "notification": notification}

    def retrain_model(algorithm: str = "random_forest") -> dict:
        return {"status": "disabled", "algorithm": algorithm}

    def run_data_pipeline(payload: dict) -> dict:
        return {"status": "disabled", "payload": payload}

    def ingest_firms_hotspots(region_ids: list[str] | None = None) -> dict:
        return {"status": "disabled", "reason": "Celery is not installed", "region_ids": region_ids or "all"}

    def acquire_latest_sentinel_scene(region_ids: list[str] | None = None) -> dict:
        return {"status": "disabled", "reason": "Celery is not installed", "region_ids": region_ids or "all"}

    def prepare_sentinel_raster(region_id: str, scene_id: str | None = None) -> dict:
        return {"status": "disabled", "reason": "Celery is not installed", "region_id": region_id, "scene_id": scene_id}

    def apply_sentinel_quality_mask(region_id: str, scene_id: str | None = None) -> dict:
        return {"status": "disabled", "reason": "Celery is not installed", "region_id": region_id, "scene_id": scene_id}

    def calculate_sentinel_ndvi(region_id: str, scene_id: str | None = None) -> dict:
        return {"status": "disabled", "reason": "Celery is not installed", "region_id": region_id, "scene_id": scene_id}
