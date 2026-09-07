from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
import csv
import logging

logger = logging.getLogger("firesight.data.quality")

OUTLIER_Z_SCORE = 3.0
DRIFT_RELATIVE_THRESHOLD = 0.2


@dataclass(frozen=True)
class DataQualityReport:
    """Dataset quality metrics used before storage, training, and analytics."""

    record_count: int
    missing_values: dict[str, int]
    duplicate_records: int
    outliers: dict[str, int]
    class_distribution: dict[str, int] = field(default_factory=dict)
    feature_statistics: dict[str, dict[str, float]] = field(default_factory=dict)
    drift: dict[str, float] = field(default_factory=dict)

    @property
    def quality_score(self) -> float:
        total_issues = sum(self.missing_values.values()) + self.duplicate_records + sum(self.outliers.values())
        if self.record_count == 0:
            return 0.0
        return round(max(0.0, 1.0 - (total_issues / max(self.record_count, 1))), 4)


class DataQualityAnalyzer:
    """Generate data quality reports for tabular environmental datasets."""

    def analyze_csv(self, path: Path, label_field: str | None = None, baseline_statistics: dict[str, dict[str, float]] | None = None) -> DataQualityReport:
        rows = self._read_rows(path)
        if not rows:
            return DataQualityReport(record_count=0, missing_values={}, duplicate_records=0, outliers={})
        fields = list(rows[0].keys())
        missing_values = {field: sum(1 for row in rows if row.get(field) in {"", None}) for field in fields}
        duplicate_records = len(rows) - len({tuple(row.get(field, "") for field in fields) for row in rows})
        numeric_columns = self._numeric_columns(rows, fields)
        feature_statistics = {field: self._statistics(values) for field, values in numeric_columns.items()}
        outliers = {field: self._outlier_count(values) for field, values in numeric_columns.items()}
        class_distribution = self._class_distribution(rows, label_field) if label_field else {}
        drift = self._drift(feature_statistics, baseline_statistics or {})
        logger.info("data_quality_report_created path=%s rows=%s score=%.4f", path, len(rows), DataQualityReport(len(rows), missing_values, duplicate_records, outliers).quality_score)
        return DataQualityReport(
            record_count=len(rows),
            missing_values=missing_values,
            duplicate_records=duplicate_records,
            outliers=outliers,
            class_distribution=class_distribution,
            feature_statistics=feature_statistics,
            drift=drift,
        )

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def _numeric_columns(self, rows: list[dict[str, str]], fields: list[str]) -> dict[str, list[float]]:
        columns: dict[str, list[float]] = {}
        for field in fields:
            values: list[float] = []
            for row in rows:
                value = row.get(field)
                if value in {"", None}:
                    continue
                try:
                    values.append(float(value))
                except ValueError:
                    values = []
                    break
            if values:
                columns[field] = values
        return columns

    def _statistics(self, values: list[float]) -> dict[str, float]:
        return {
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "mean": round(mean(values), 4),
            "std": round(pstdev(values), 4) if len(values) > 1 else 0.0,
        }

    def _outlier_count(self, values: list[float]) -> int:
        if len(values) < 3:
            return 0
        average = mean(values)
        deviation = pstdev(values)
        if deviation == 0:
            return 0
        return sum(1 for value in values if abs((value - average) / deviation) > OUTLIER_Z_SCORE)

    def _class_distribution(self, rows: list[dict[str, str]], label_field: str | None) -> dict[str, int]:
        distribution: dict[str, int] = {}
        for row in rows:
            label = row.get(label_field or "")
            if label:
                distribution[label] = distribution.get(label, 0) + 1
        return distribution

    def _drift(self, current: dict[str, dict[str, float]], baseline: dict[str, dict[str, float]]) -> dict[str, float]:
        drift: dict[str, float] = {}
        for field, statistics in current.items():
            baseline_mean = baseline.get(field, {}).get("mean")
            if baseline_mean in {None, 0}:
                continue
            drift[field] = round(abs(statistics["mean"] - baseline_mean) / abs(baseline_mean), 4)
        return {field: value for field, value in drift.items() if value >= DRIFT_RELATIVE_THRESHOLD}
