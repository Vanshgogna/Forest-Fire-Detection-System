from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from backend.core.config import get_settings
from backend.core.security import Principal, require_admin, require_researcher
from backend.data.pipeline import DataPipeline, PipelineManifest
from backend.data.sources import DataSource, RefreshPolicy
from backend.schemas.data import PipelineRunRequest

router = APIRouter()


def _pipeline() -> DataPipeline:
    settings = get_settings()
    return DataPipeline(
        dataset_root=Path(settings.dataset_dir),
        cache_root=Path(settings.cache_artifact_dir) / "data-pipeline",
        archive_root=Path(settings.data_archive_dir),
        checkpoint_root=Path(settings.data_checkpoint_dir),
    )


def _manifest(payload: PipelineRunRequest) -> PipelineManifest:
    return PipelineManifest(
        dataset_id=payload.dataset_id,
        dataset_version=payload.dataset_version,
        source=DataSource(
            name=payload.source.name,
            kind=payload.source.kind,
            uri=payload.source.uri,
            expected_checksum=payload.source.expected_checksum,
            version=payload.source.version,
            metadata=payload.source.metadata,
            refresh_policy=RefreshPolicy(
                mode=payload.source.refresh_mode,
                schedule_cron=payload.source.schedule_cron,
                incremental_field=payload.source.incremental_field,
                last_watermark=payload.source.last_watermark,
                checkpoint_enabled=payload.source.checkpoint_enabled,
            ),
        ),
        storage_format=payload.storage_format,
        required_fields=payload.required_fields,
        coordinate_fields=payload.coordinate_fields,
        label_field=payload.label_field,
        expected_crs=payload.expected_crs,
        baseline_statistics=payload.baseline_statistics,
        model_version_compatibility=payload.model_version_compatibility,
    )


@router.get("/sources")
def data_sources(_: Principal = Depends(require_researcher)):
    return {
        "supported_sources": [
            "Sentinel-2",
            "MODIS",
            "Weather API",
            "Historical Fire Records",
            "GeoJSON",
            "Raster File",
            "CSV",
            "Shapefile",
            "Future Satellite Provider",
        ],
        "pipeline_stages": ["extract", "transform", "validate", "normalize", "enrich", "store", "quality", "archive", "version", "cache"],
        "refresh_modes": ["manual", "scheduled", "incremental"],
    }


@router.post("/pipeline/run")
def run_pipeline(payload: PipelineRunRequest, _: Principal = Depends(require_admin)):
    result = _pipeline().run(_manifest(payload))
    return result.to_dict()


@router.post("/pipeline/resume")
def resume_pipeline(payload: PipelineRunRequest, _: Principal = Depends(require_admin)):
    return _pipeline().resume(_manifest(payload))
