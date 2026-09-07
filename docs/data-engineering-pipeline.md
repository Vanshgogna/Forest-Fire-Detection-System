# Data Engineering Pipeline

FireSight uses a modular ETL pipeline for environmental datasets that feed GIS layers, remote-sensing analysis, weather intelligence, and ML training.

## Data Sources

Supported source contracts:

- Sentinel-2 scene metadata and raster products
- MODIS hotspot feeds
- Weather API exports
- Historical fire records
- GeoJSON boundaries and risk layers
- Raster files such as GeoTIFF, TIFF, and JP2
- CSV tabular datasets
- Shapefiles with `.shp`, `.shx`, and `.dbf` sidecars
- Future satellite providers through the same `DataSource` interface

Each source can define a refresh policy:

- `manual`: operator-triggered or API-triggered loads.
- `scheduled`: Celery-compatible refreshes with a cron expression.
- `incremental`: loads gated by a configured watermark field and last processed watermark.

## Ingestion

`DataIngestionClient` supports:

- Automatic downloads from HTTP/HTTPS URLs.
- Local file ingestion for CSV, GeoJSON, rasters, and shapefiles.
- Scheduled downloads through `firesight.run_data_pipeline`.
- Incremental skip behavior when a destination file already matches the expected checksum.
- Retry with backoff for remote downloads.
- SHA-256 checksum validation and integrity verification.
- Download progress through byte-count callbacks and persisted `DownloadResult.progress_bytes`.

## ETL Stages

Every stage is exposed as a separate method on `DataPipeline`:

1. Extract: copy local files or download remote URLs with retry, progress callbacks, and checksum validation.
2. Transform: move source files into processed storage and normalize CSV whitespace.
3. Validate: check missing files, empty files, malformed CSV/GeoJSON, invalid coordinates, invalid CRS, missing weather fields, missing labels, raster signatures, raster extension support, and shapefile sidecars.
4. Normalize: publish transformed files under canonical processed paths.
5. Enrich: preserve source kind, storage format, and compatibility metadata for downstream feature generation.
6. Store: make processed files available to the application dataset directory.
7. Quality: report missing values, duplicate records, outliers, class distribution, feature statistics, and dataset drift against a baseline.
8. Archive: copy validated processed files to durable archive storage.
9. Version: write dataset metadata with dataset version, download time, source, processing version, compatible model versions, checksum, and record count.
10. Cache: store quality reports for dashboard/admin inspection.

Each run also writes a checkpoint with status, completed stages, the next stage, resumability, and validation errors.

## Validation Rules

- Coordinates must be within latitude `-90..90` and longitude `-180..180`.
- CRS values must use supported identifiers such as `EPSG:4326` or OGC CRS URNs.
- CSV datasets must include configured required fields.
- Training datasets must include configured label fields.
- Weather records require temperature, humidity, wind speed, and rainfall.
- GeoJSON must parse as JSON and use a supported geometry or feature type.
- Raster files must use supported extensions and recognizable TIFF/JP2 signatures.
- Shapefiles must include required sidecar files.

## Data Versioning

`DatasetVersionStore` persists one JSON manifest per processed dataset version with:

- Dataset ID and dataset version.
- Download timestamp.
- Source name and source kind.
- Processing version.
- Model version compatibility list.
- SHA-256 checksum.
- Record count.
- Storage format metadata.

This links training and inference artifacts back to the exact source, processing code, and compatible model families.

## Data Quality

`DataQualityAnalyzer` generates reports for CSV datasets:

- Missing values per field.
- Duplicate record count.
- Outlier count per numeric feature.
- Class distribution for configured label fields.
- Feature statistics: min, max, mean, and standard deviation.
- Dataset drift against configured baseline statistics.
- A quality score derived from missing values, duplicates, and outliers.

## Storage Format

Default local layout:

```text
datasets/
├── raw/<dataset_id>/<dataset_version>/source.<format>
├── processed/<dataset_id>/<dataset_version>/normalized.<format>
└── versions/<dataset_id>-<dataset_version>.json

backend/artifacts/
├── data-archive/<dataset_id>/<dataset_version>/
├── data-checkpoints/<dataset_id>-<dataset_version>.json
└── cache/data-pipeline/
```

Production deployments should map archive, raster, and report artifacts to managed object storage.

## Automation

The pipeline is callable from:

- `DataPipeline.run()` for direct service use.
- `/api/data/pipeline/run` for admin-triggered ETL.
- `firesight.run_data_pipeline` for Celery worker execution.
- `PipelineAutomationPlanner` for scheduled and incremental worker plans.

Retries are handled at ingestion time. Failed validations create checkpoints and stop before archive/version stages, allowing operators to inspect errors and rerun with corrected data. The checkpoint includes the next stage and a `resumable` flag for failure recovery and pipeline resume workflows.

## Documentation Output

This document is the generated data-pipeline contract for operators and developers. It explains:

- Data sources.
- Processing steps.
- Transformation rules.
- Validation rules.
- Storage format.
- Directory structure.

## API Contracts

- `GET /api/data/sources`: researcher/admin-visible source and stage contract.
- `POST /api/data/pipeline/run`: admin-only ETL execution.
- `POST /api/data/pipeline/resume`: admin-only checkpoint inspection.

All data API requests use strict schemas and reject unexpected fields.
