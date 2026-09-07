from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import csv
import json
import logging
import shutil

from backend.data.quality import DataQualityAnalyzer, DataQualityReport
from backend.data.sources import DataIngestionClient, DataSource, DownloadResult, SourceKind, sha256_file
from backend.data.validation import DataValidationResult, DataValidator
from backend.data.versioning import DatasetVersion, DatasetVersionStore

logger = logging.getLogger("firesight.data.pipeline")

PROCESSING_VERSION = "etl-2026.08"
DEFAULT_MODEL_COMPATIBILITY = ["wildfire-risk-rf-v1", "wildfire-risk-xgb-v1"]
STAGE_ORDER = ["extract", "transform", "validate", "normalize", "enrich", "store", "quality", "archive", "version", "cache"]


@dataclass(frozen=True)
class PipelineManifest:
    """Full configuration for one modular ETL run."""

    dataset_id: str
    dataset_version: str
    source: DataSource
    storage_format: str
    required_fields: list[str] = field(default_factory=list)
    coordinate_fields: tuple[str, str] | None = None
    label_field: str | None = None
    expected_crs: str | None = "EPSG:4326"
    baseline_statistics: dict[str, dict[str, float]] = field(default_factory=dict)
    model_version_compatibility: list[str] = field(default_factory=lambda: DEFAULT_MODEL_COMPATIBILITY.copy())


@dataclass(frozen=True)
class PipelineResult:
    """Operational result from extract, transform, validate, store, cache, and archive stages."""

    dataset_id: str
    status: str
    stages: list[str]
    downloaded_path: str
    normalized_path: str | None
    archive_path: str | None
    checkpoint_path: str
    version_manifest_path: str | None
    validation: DataValidationResult
    quality: DataQualityReport | None
    dataset_version: DatasetVersion | None
    download: DownloadResult

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "status": self.status,
            "stages": self.stages,
            "downloaded_path": self.downloaded_path,
            "normalized_path": self.normalized_path,
            "archive_path": self.archive_path,
            "checkpoint_path": self.checkpoint_path,
            "version_manifest_path": self.version_manifest_path,
            "validation": asdict(self.validation),
            "quality": asdict(self.quality) if self.quality else None,
            "dataset_version": self.dataset_version.to_dict() if self.dataset_version else None,
            "download": asdict(self.download),
        }


class DataPipeline:
    """Run enterprise ETL stages for fire-risk, GIS, weather, raster, and satellite data."""

    def __init__(self, dataset_root: Path, cache_root: Path, archive_root: Path, checkpoint_root: Path):
        self.dataset_root = dataset_root
        self.cache_root = cache_root
        self.archive_root = archive_root
        self.checkpoint_root = checkpoint_root
        self.ingestion = DataIngestionClient()
        self.validator = DataValidator()
        self.quality = DataQualityAnalyzer()
        self.version_store = DatasetVersionStore(dataset_root / "versions")
        for directory in [self.dataset_root, self.cache_root, self.archive_root, self.checkpoint_root]:
            directory.mkdir(parents=True, exist_ok=True)

    def run(self, manifest: PipelineManifest) -> PipelineResult:
        stages: list[str] = []
        checkpoint_path = self._checkpoint_path(manifest)
        try:
            downloaded_path, download = self.extract(manifest)
            stages.append("extract")
            normalized_path = self.transform(manifest, downloaded_path)
            stages.append("transform")
            validation = self.validate(manifest, normalized_path)
            stages.append("validate")
            if not validation.valid:
                self._write_checkpoint(checkpoint_path, "failed_validation", stages, validation.errors)
                return self._result(manifest, "failed_validation", stages, downloaded_path, normalized_path, None, checkpoint_path, None, validation, None, download)
            stages.extend(["normalize", "enrich", "store"])
            quality = self.profile_quality(manifest, normalized_path)
            stages.append("quality")
            archive_path = self.archive(manifest, normalized_path)
            stages.append("archive")
            dataset_version = self.version(manifest, normalized_path, validation.record_count)
            version_manifest_path = self.version_store.save(dataset_version)
            stages.append("version")
            self.cache(manifest, quality)
            stages.append("cache")
            self._write_checkpoint(checkpoint_path, "completed", stages, [])
            logger.info("data_pipeline_completed dataset_id=%s version=%s", manifest.dataset_id, manifest.dataset_version)
            return self._result(manifest, "completed", stages, downloaded_path, normalized_path, archive_path, checkpoint_path, version_manifest_path, validation, quality, download)
        except Exception as exc:
            self._write_checkpoint(checkpoint_path, "failed", stages, [exc.__class__.__name__])
            logger.error("data_pipeline_failed dataset_id=%s error_type=%s", manifest.dataset_id, exc.__class__.__name__)
            raise

    def extract(self, manifest: PipelineManifest) -> tuple[Path, DownloadResult]:
        suffix = Path(manifest.source.uri).suffix or f".{manifest.storage_format.lower()}"
        destination = self.dataset_root / "raw" / manifest.dataset_id / manifest.dataset_version / f"source{suffix}"
        download = self.ingestion.ingest(manifest.source, destination)
        return destination, download

    def transform(self, manifest: PipelineManifest, path: Path) -> Path:
        normalized = self.dataset_root / "processed" / manifest.dataset_id / manifest.dataset_version / f"normalized.{manifest.storage_format.lower()}"
        normalized.parent.mkdir(parents=True, exist_ok=True)
        if manifest.storage_format.lower() == "csv":
            self._normalize_csv(path, normalized)
        else:
            shutil.copyfile(path, normalized)
        return normalized

    def validate(self, manifest: PipelineManifest, path: Path) -> DataValidationResult:
        storage_format = manifest.storage_format.lower()
        if storage_format == "csv":
            return self.validator.validate_csv(
                path,
                manifest.required_fields,
                manifest.coordinate_fields,
                manifest.label_field,
                weather_fields_required=manifest.source.kind == SourceKind.WEATHER_API,
            )
        if storage_format == "geojson":
            return self.validator.validate_geojson(path)
        if storage_format in {"tif", "tiff", "jp2", "raster"}:
            return self.validator.validate_raster(path, manifest.expected_crs)
        if storage_format == "shapefile":
            return self.validator.validate_shapefile(path)
        return DataValidationResult(valid=False, errors=[f"unsupported storage format: {manifest.storage_format}"])

    def profile_quality(self, manifest: PipelineManifest, path: Path) -> DataQualityReport | None:
        if manifest.storage_format.lower() != "csv":
            return None
        return self.quality.analyze_csv(path, manifest.label_field, manifest.baseline_statistics)

    def archive(self, manifest: PipelineManifest, path: Path) -> Path:
        archive_path = self.archive_root / manifest.dataset_id / manifest.dataset_version / path.name
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, archive_path)
        return archive_path

    def version(self, manifest: PipelineManifest, path: Path, record_count: int) -> DatasetVersion:
        checksum = sha256_file(path)
        return DatasetVersion.create(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.dataset_version,
            source=manifest.source.name,
            processing_version=PROCESSING_VERSION,
            model_version_compatibility=manifest.model_version_compatibility,
            checksum=checksum,
            record_count=record_count,
            metadata={"storage_format": manifest.storage_format, "source_kind": manifest.source.kind.value},
        )

    def cache(self, manifest: PipelineManifest, quality: DataQualityReport | None) -> Path:
        cache_path = self.cache_root / "quality" / f"{manifest.dataset_id}-{manifest.dataset_version}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(asdict(quality) if quality else {"status": "not_applicable"}, indent=2, sort_keys=True), encoding="utf-8")
        return cache_path

    def resume(self, manifest: PipelineManifest) -> dict:
        checkpoint_path = self._checkpoint_path(manifest)
        if not checkpoint_path.exists():
            return {"resumable": False, "reason": "checkpoint not found"}
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        return {"resumable": checkpoint.get("status") not in {"completed"}, **checkpoint}

    def _normalize_csv(self, input_path: Path, output_path: Path) -> None:
        with input_path.open(newline="", encoding="utf-8") as input_file:
            reader = csv.DictReader(input_file)
            fieldnames = reader.fieldnames or []
            with output_path.open("w", newline="", encoding="utf-8") as output_file:
                writer = csv.DictWriter(output_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    writer.writerow({field: (row.get(field) or "").strip() for field in fieldnames})

    def _checkpoint_path(self, manifest: PipelineManifest) -> Path:
        return self.checkpoint_root / f"{manifest.dataset_id}-{manifest.dataset_version}.json"

    def _write_checkpoint(self, checkpoint_path: Path, status: str, stages: list[str], errors: list[str]) -> None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        next_stage = self._next_stage(stages)
        checkpoint_path.write_text(
            json.dumps(
                {
                    "status": status,
                    "completed_stages": stages,
                    "next_stage": next_stage,
                    "resumable": status != "completed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def _next_stage(self, stages: list[str]) -> str | None:
        completed = set(stages)
        return next((stage for stage in STAGE_ORDER if stage not in completed), None)

    def _result(
        self,
        manifest: PipelineManifest,
        status: str,
        stages: list[str],
        downloaded_path: Path,
        normalized_path: Path | None,
        archive_path: Path | None,
        checkpoint_path: Path,
        version_manifest_path: Path | None,
        validation: DataValidationResult,
        quality: DataQualityReport | None,
        download: DownloadResult,
    ) -> PipelineResult:
        dataset_version = None
        if version_manifest_path:
            dataset_version = self.version_store.load(manifest.dataset_id, manifest.dataset_version)
        return PipelineResult(
            dataset_id=manifest.dataset_id,
            status=status,
            stages=stages,
            downloaded_path=str(downloaded_path),
            normalized_path=str(normalized_path) if normalized_path else None,
            archive_path=str(archive_path) if archive_path else None,
            checkpoint_path=str(checkpoint_path),
            version_manifest_path=str(version_manifest_path) if version_manifest_path else None,
            validation=validation,
            quality=quality,
            dataset_version=dataset_version,
            download=download,
        )
