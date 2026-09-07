from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.parse import urlparse
import httpx
import logging
import shutil

try:
    from backend.core.errors import ExternalServiceError
except ModuleNotFoundError:  # pragma: no cover - supports standalone ETL environments without FastAPI installed.
    class ExternalServiceError(RuntimeError):
        pass

logger = logging.getLogger("firesight.data.sources")

DOWNLOAD_CHUNK_BYTES = 1024 * 1024
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25


class SourceKind(str, Enum):
    SENTINEL_2 = "Sentinel-2"
    MODIS = "MODIS"
    WEATHER_API = "Weather API"
    HISTORICAL_FIRE = "Historical Fire Records"
    GEOJSON = "GeoJSON"
    RASTER = "Raster File"
    CSV = "CSV"
    SHAPEFILE = "Shapefile"
    FUTURE_SATELLITE = "Future Satellite Provider"


class RefreshMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    INCREMENTAL = "incremental"


@dataclass(frozen=True)
class RefreshPolicy:
    """Refresh rules for automatic, scheduled, and incremental dataset ingestion."""

    mode: RefreshMode = RefreshMode.MANUAL
    schedule_cron: str | None = None
    incremental_field: str | None = None
    last_watermark: str | None = None
    checkpoint_enabled: bool = True


@dataclass(frozen=True)
class DataSource:
    """Configuration for one ingestible environmental data source."""

    name: str
    kind: SourceKind
    uri: str
    expected_checksum: str | None = None
    version: str = "v1"
    metadata: dict[str, str] = field(default_factory=dict)
    refresh_policy: RefreshPolicy = field(default_factory=RefreshPolicy)

    @property
    def is_remote(self) -> bool:
        return urlparse(self.uri).scheme in {"http", "https"}


@dataclass(frozen=True)
class DownloadResult:
    """Result metadata for a completed or skipped download."""

    source: str
    destination: str
    checksum: str
    bytes_written: int
    skipped: bool
    progress_bytes: list[int] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    """Calculate a SHA-256 checksum for integrity verification."""
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected_checksum: str | None) -> str:
    """Return the actual checksum and reject mismatches when an expected value is supplied."""
    actual_checksum = sha256_file(path)
    if expected_checksum and actual_checksum.lower() != expected_checksum.lower():
        logger.warning("dataset_checksum_mismatch path=%s", path)
        raise ValueError("Downloaded dataset checksum does not match the expected checksum")
    return actual_checksum


class DataIngestionClient:
    """Download or copy source datasets with retry, progress, and checksum validation."""

    def __init__(self, retry_attempts: int = DEFAULT_RETRY_ATTEMPTS, retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS):
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    def ingest(self, source: DataSource, destination: Path, progress: Callable[[int], None] | None = None) -> DownloadResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        progress_bytes: list[int] = []

        def track_progress(bytes_written: int) -> None:
            progress_bytes.append(bytes_written)
            if progress:
                progress(bytes_written)

        if destination.exists() and source.expected_checksum:
            checksum = sha256_file(destination)
            if checksum.lower() == source.expected_checksum.lower():
                logger.info("dataset_ingest_skipped source=%s reason=checksum_match", source.name)
                bytes_written = destination.stat().st_size
                return DownloadResult(
                    source=source.name,
                    destination=str(destination),
                    checksum=checksum,
                    bytes_written=bytes_written,
                    skipped=True,
                    progress_bytes=[bytes_written],
                )

        if source.is_remote:
            bytes_written = self._download_remote(source.uri, destination, track_progress)
        else:
            bytes_written = self._copy_local(Path(source.uri), destination, track_progress)
        checksum = verify_checksum(destination, source.expected_checksum)
        logger.info("dataset_ingested source=%s bytes=%s checksum=%s", source.name, bytes_written, checksum[:12])
        return DownloadResult(
            source=source.name,
            destination=str(destination),
            checksum=checksum,
            bytes_written=bytes_written,
            skipped=False,
            progress_bytes=progress_bytes or [bytes_written],
        )

    def _copy_local(self, source_path: Path, destination: Path, progress: Callable[[int], None] | None) -> int:
        if not source_path.exists():
            raise FileNotFoundError(f"Dataset source file does not exist: {source_path}")
        bytes_written = 0
        with source_path.open("rb") as source_file, destination.open("wb") as target_file:
            for chunk in iter(lambda: source_file.read(DOWNLOAD_CHUNK_BYTES), b""):
                target_file.write(chunk)
                bytes_written += len(chunk)
                if progress:
                    progress(bytes_written)
        return bytes_written

    def _download_remote(self, uri: str, destination: Path, progress: Callable[[int], None] | None) -> int:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return self._stream_remote(uri, destination, progress)
            except (OSError, httpx.HTTPError) as exc:
                last_error = exc
                logger.warning("dataset_download_retry uri=%s attempt=%s", uri, attempt)
                if attempt < self.retry_attempts:
                    sleep(self.retry_backoff_seconds * attempt)
        raise ExternalServiceError("Dataset source could not be downloaded") from last_error

    def _stream_remote(self, uri: str, destination: Path, progress: Callable[[int], None] | None) -> int:
        scheme = urlparse(uri).scheme
        if scheme not in {"http", "https"}:
            raise ValueError("Remote dataset sources must use HTTP or HTTPS.")
        temporary_path = destination.with_suffix(destination.suffix + ".download")
        bytes_written = 0
        with httpx.stream("GET", uri, timeout=30.0, follow_redirects=True) as response, temporary_path.open("wb") as target_file:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_BYTES):
                target_file.write(chunk)
                bytes_written += len(chunk)
                if progress:
                    progress(bytes_written)
        shutil.move(str(temporary_path), destination)
        return bytes_written
