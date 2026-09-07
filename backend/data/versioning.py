from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

logger = logging.getLogger("firesight.data.versioning")


@dataclass(frozen=True)
class DatasetVersion:
    """Metadata linking a processed dataset to source, processing, and model compatibility."""

    dataset_id: str
    dataset_version: str
    source: str
    downloaded_at: str
    processing_version: str
    model_version_compatibility: list[str]
    checksum: str
    record_count: int
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        dataset_id: str,
        dataset_version: str,
        source: str,
        processing_version: str,
        model_version_compatibility: list[str],
        checksum: str,
        record_count: int,
        metadata: dict[str, str] | None = None,
    ) -> "DatasetVersion":
        return cls(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source=source,
            downloaded_at=datetime.now(timezone.utc).isoformat(),
            processing_version=processing_version,
            model_version_compatibility=model_version_compatibility,
            checksum=checksum,
            record_count=record_count,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict:
        return asdict(self)


class DatasetVersionStore:
    """Persist dataset version manifests as JSON metadata for workers and APIs."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, version: DatasetVersion) -> Path:
        path = self.root / f"{version.dataset_id}-{version.dataset_version}.json"
        path.write_text(json.dumps(version.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        logger.info("dataset_version_saved dataset_id=%s version=%s", version.dataset_id, version.dataset_version)
        return path

    def load(self, dataset_id: str, dataset_version: str) -> DatasetVersion:
        path = self.root / f"{dataset_id}-{dataset_version}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DatasetVersion(**payload)
