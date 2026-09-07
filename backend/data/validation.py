from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
import json
import logging

logger = logging.getLogger("firesight.data.validation")

SUPPORTED_RASTER_SUFFIXES = {".tif", ".tiff", ".jp2"}
SHAPEFILE_REQUIRED_SUFFIXES = {".shp", ".shx", ".dbf"}
SUPPORTED_CRS_PREFIXES = ("EPSG:", "urn:ogc:def:crs:")
WEATHER_REQUIRED_FIELDS = ["temperature", "humidity", "wind_speed", "rainfall"]
MIN_RASTER_BYTES = 8


@dataclass(frozen=True)
class DataValidationResult:
    """Validation outcome for raw or transformed environmental datasets."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    record_count: int = 0


def _is_valid_coordinate(latitude: float, longitude: float) -> bool:
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


class DataValidator:
    """Validate CSV, GeoJSON, raster, weather, fire-label, and shapefile datasets."""

    def validate_file_exists(self, path: Path) -> DataValidationResult:
        if not path.exists():
            return DataValidationResult(valid=False, errors=["dataset file is missing"])
        if path.is_file() and path.stat().st_size == 0:
            return DataValidationResult(valid=False, errors=["dataset file is empty"])
        return DataValidationResult(valid=True)

    def validate_csv(
        self,
        path: Path,
        required_fields: list[str],
        coordinate_fields: tuple[str, str] | None = None,
        label_field: str | None = None,
        weather_fields_required: bool = False,
    ) -> DataValidationResult:
        existence = self.validate_file_exists(path)
        if not existence.valid:
            return existence
        errors: list[str] = []
        warnings: list[str] = []
        duplicate_keys: set[tuple[str, ...]] = set()
        rows_seen = 0
        duplicate_count = 0
        try:
            with path.open(newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames or []
                missing_weather_fields: list[str] = []
                missing_fields = [field for field in required_fields if field not in fieldnames]
                if missing_fields:
                    errors.append(f"missing required fields: {', '.join(missing_fields)}")
                if weather_fields_required:
                    missing_weather_fields = [field for field in WEATHER_REQUIRED_FIELDS if field not in fieldnames]
                    if missing_weather_fields:
                        errors.append(f"missing weather fields: {', '.join(missing_weather_fields)}")
                if label_field and label_field not in fieldnames:
                    errors.append(f"missing label field: {label_field}")
                for row in reader:
                    rows_seen += 1
                    key = tuple(row.get(field, "") for field in fieldnames)
                    if key in duplicate_keys:
                        duplicate_count += 1
                    duplicate_keys.add(key)
                    if coordinate_fields:
                        latitude_field, longitude_field = coordinate_fields
                        try:
                            latitude = float(row.get(latitude_field, ""))
                            longitude = float(row.get(longitude_field, ""))
                        except ValueError:
                            errors.append(f"invalid coordinates at row {rows_seen}")
                            continue
                        if not _is_valid_coordinate(latitude, longitude):
                            errors.append(f"coordinate out of range at row {rows_seen}")
                    if weather_fields_required:
                        weather_result = self.validate_weather_record(row)
                        for error in weather_result.errors:
                            if missing_weather_fields and error.startswith("missing weather fields:"):
                                continue
                            errors.append(f"{error} at row {rows_seen}")
                if duplicate_count:
                    warnings.append(f"duplicate records detected: {duplicate_count}")
        except UnicodeDecodeError:
            errors.append("csv file is not valid UTF-8")
        except csv.Error:
            errors.append("csv file is malformed")
        logger.info("csv_dataset_validated path=%s valid=%s rows=%s", path, not errors, rows_seen)
        return DataValidationResult(valid=not errors, errors=errors, warnings=warnings, record_count=rows_seen)

    def validate_geojson(self, path: Path) -> DataValidationResult:
        existence = self.validate_file_exists(path)
        if not existence.valid:
            return existence
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return DataValidationResult(valid=False, errors=["geojson file is malformed"])
        errors = []
        if payload.get("type") not in {"FeatureCollection", "Feature", "Polygon", "MultiPolygon", "Point", "MultiPoint", "LineString", "MultiLineString"}:
            errors.append("geojson type is unsupported or missing")
        features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
        if payload.get("type") == "FeatureCollection" and not isinstance(features, list):
            errors.append("geojson features must be a list")
        crs = payload.get("crs", {}).get("properties", {}).get("name")
        if crs and not self.validate_crs(crs):
            errors.append("geojson CRS is invalid")
        return DataValidationResult(valid=not errors, errors=errors, record_count=len(features) if isinstance(features, list) else 0)

    def validate_raster(self, path: Path, expected_crs: str | None = None) -> DataValidationResult:
        existence = self.validate_file_exists(path)
        if not existence.valid:
            return existence
        errors = []
        if path.suffix.lower() not in SUPPORTED_RASTER_SUFFIXES:
            errors.append("raster file extension is unsupported")
        if path.stat().st_size < MIN_RASTER_BYTES:
            errors.append("raster file is truncated or corrupted")
        elif not self._has_supported_raster_signature(path):
            errors.append("raster file signature is invalid")
        if expected_crs and not self.validate_crs(expected_crs):
            errors.append("raster CRS is invalid")
        return DataValidationResult(valid=not errors, errors=errors, record_count=1 if not errors else 0)

    def validate_shapefile(self, shp_path: Path) -> DataValidationResult:
        base = shp_path.with_suffix("")
        missing = [suffix for suffix in SHAPEFILE_REQUIRED_SUFFIXES if not base.with_suffix(suffix).exists()]
        if missing:
            return DataValidationResult(valid=False, errors=[f"missing shapefile sidecars: {', '.join(sorted(missing))}"])
        return DataValidationResult(valid=True, record_count=1)

    def validate_weather_record(self, record: dict) -> DataValidationResult:
        missing = [field for field in WEATHER_REQUIRED_FIELDS if record.get(field) in {None, ""}]
        errors = [f"missing weather fields: {', '.join(missing)}"] if missing else []
        numeric_values: dict[str, float] = {}
        for field in WEATHER_REQUIRED_FIELDS:
            if field in missing:
                continue
            try:
                numeric_values[field] = float(record[field])
            except (TypeError, ValueError):
                errors.append(f"{field} must be numeric")
        if "humidity" in numeric_values and not 0 <= numeric_values["humidity"] <= 100:
            errors.append("humidity must be between 0 and 100")
        if "wind_speed" in numeric_values and numeric_values["wind_speed"] < 0:
            errors.append("wind_speed must be non-negative")
        if "rainfall" in numeric_values and numeric_values["rainfall"] < 0:
            errors.append("rainfall must be non-negative")
        return DataValidationResult(valid=not errors, errors=errors, record_count=1 if not errors else 0)

    def validate_crs(self, crs: str) -> bool:
        normalized = crs.strip()
        return any(normalized.startswith(prefix) for prefix in SUPPORTED_CRS_PREFIXES)

    def _has_supported_raster_signature(self, path: Path) -> bool:
        header = path.read_bytes()[:16]
        if path.suffix.lower() in {".tif", ".tiff"}:
            return header.startswith((b"II*\x00", b"MM\x00*"))
        if path.suffix.lower() == ".jp2":
            return header.startswith(b"\x00\x00\x00\x0cjP  \r\n\x87\n") or b"ftypjp2" in header
        return False
