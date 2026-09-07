from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import resource
import time
from threading import Lock
from typing import Callable


SLOW_API_THRESHOLD_MS = 750.0
SLOW_PREDICTION_THRESHOLD_MS = 500.0
SLOW_RASTER_THRESHOLD_MS = 2_000.0
HIGH_ERROR_RATE_THRESHOLD = 0.05


@dataclass(frozen=True)
class MetricSample:
    name: str
    value: float
    unit: str
    labels: dict[str, str]
    recorded_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class ObservabilityRegistry:
    """In-process metrics, health, and monitoring registry for API deployments."""

    def __init__(self, max_samples: int = 500):
        self.max_samples = max_samples
        self._lock = Lock()
        self._requests: deque[MetricSample] = deque(maxlen=max_samples)
        self._predictions: deque[MetricSample] = deque(maxlen=max_samples)
        self._rasters: deque[MetricSample] = deque(maxlen=max_samples)
        self._database_queries: deque[MetricSample] = deque(maxlen=max_samples)
        self._errors: deque[MetricSample] = deque(maxlen=max_samples)
        self._cache_hits = 0
        self._cache_misses = 0
        self._model_outcomes: deque[dict] = deque(maxlen=max_samples)
        self._dataset_failures: deque[dict] = deque(maxlen=max_samples)

    def record_api_request(self, method: str, path: str, status_code: int, elapsed_ms: float) -> None:
        labels = {"method": method, "path": path, "status_code": str(status_code)}
        self._append(self._requests, MetricSample("api_response_time", round(elapsed_ms, 4), "ms", labels, self._now()))
        if status_code >= 500:
            self._append(self._errors, MetricSample("api_error", 1, "count", labels, self._now()))

    def record_prediction(self, risk_category: str, confidence: int, elapsed_ms: float, model_version: str) -> None:
        labels = {"risk_category": risk_category, "model_version": model_version}
        self._append(self._predictions, MetricSample("prediction_time", round(elapsed_ms, 4), "ms", labels, self._now()))
        with self._lock:
            self._model_outcomes.append(
                {
                    "risk_category": risk_category,
                    "confidence": confidence,
                    "elapsed_ms": round(elapsed_ms, 4),
                    "model_version": model_version,
                    "recorded_at": self._now(),
                }
            )

    def record_raster_processing(self, operation: str, elapsed_ms: float, status: str = "ok") -> None:
        labels = {"operation": operation, "status": status}
        self._append(self._rasters, MetricSample("raster_processing_time", round(elapsed_ms, 4), "ms", labels, self._now()))
        if status != "ok":
            self.record_dataset_failure("raster", operation, status)

    def record_database_query(self, operation: str, elapsed_ms: float, status: str = "ok") -> None:
        labels = {"operation": operation, "status": status}
        self._append(self._database_queries, MetricSample("database_query_time", round(elapsed_ms, 4), "ms", labels, self._now()))

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def record_dataset_failure(self, dataset_id: str, stage: str, reason: str) -> None:
        with self._lock:
            self._dataset_failures.append(
                {"dataset_id": dataset_id, "stage": stage, "reason": reason, "recorded_at": self._now()}
            )

    def application_metrics(self) -> dict:
        with self._lock:
            requests = list(self._requests)
            predictions = list(self._predictions)
            rasters = list(self._rasters)
            database_queries = list(self._database_queries)
            errors = list(self._errors)
            cache_hits = self._cache_hits
            cache_misses = self._cache_misses
        request_count = len(requests)
        error_count = len(errors)
        cache_total = cache_hits + cache_misses
        return {
            "api_response_time_ms": self._latency_summary(requests),
            "prediction_time_ms": self._latency_summary(predictions),
            "raster_processing_time_ms": self._latency_summary(rasters),
            "database_query_time_ms": self._latency_summary(database_queries),
            "memory_usage": self._memory_usage(),
            "cpu_usage": self._cpu_usage(),
            "cache_hit_rate": round(cache_hits / cache_total, 4) if cache_total else None,
            "cache": {"hits": cache_hits, "misses": cache_misses},
            "request_count": request_count,
            "error_count": error_count,
            "error_rate": round(error_count / request_count, 4) if request_count else 0.0,
        }

    def model_monitoring(self) -> dict:
        with self._lock:
            outcomes = list(self._model_outcomes)
        confidences = [item["confidence"] for item in outcomes]
        categories: dict[str, int] = {}
        for item in outcomes:
            categories[item["risk_category"]] = categories.get(item["risk_category"], 0) + 1
        return {
            "prediction_accuracy": {"status": "requires_labeled_feedback", "latest": None},
            "inference_time_ms": self._latency_summary(list(self._predictions)),
            "feature_drift": {"status": "baseline_required", "monitored_features": ["temperature", "humidity", "wind_speed", "rainfall", "ndvi", "nbr", "hotspots"]},
            "data_drift": {"status": "baseline_required", "source": "data_quality_reports"},
            "model_drift": {"status": "baseline_required", "comparison": "champion_vs_candidate"},
            "confidence_distribution": {
                "count": len(confidences),
                "average": round(sum(confidences) / len(confidences), 2) if confidences else None,
                "min": min(confidences) if confidences else None,
                "max": max(confidences) if confidences else None,
                "by_risk_category": categories,
            },
        }

    def monitoring_alerts(self) -> list[dict]:
        metrics = self.application_metrics()
        alerts: list[dict] = []
        if metrics["error_rate"] >= HIGH_ERROR_RATE_THRESHOLD:
            alerts.append(self._alert("high_error_rate", "critical", f"API error rate is {metrics['error_rate']:.2%}."))
        if (metrics["api_response_time_ms"]["p95"] or 0) >= SLOW_API_THRESHOLD_MS:
            alerts.append(self._alert("slow_api_response", "warning", "API p95 response time exceeds threshold."))
        if (metrics["prediction_time_ms"]["p95"] or 0) >= SLOW_PREDICTION_THRESHOLD_MS:
            alerts.append(self._alert("slow_prediction", "warning", "Prediction p95 latency exceeds threshold."))
        if (metrics["raster_processing_time_ms"]["p95"] or 0) >= SLOW_RASTER_THRESHOLD_MS:
            alerts.append(self._alert("slow_raster_processing", "warning", "Raster processing p95 latency exceeds threshold."))
        with self._lock:
            dataset_failures = list(self._dataset_failures)
        if dataset_failures:
            alerts.append(self._alert("dataset_failures", "critical", f"{len(dataset_failures)} dataset failures need review."))
        return alerts

    def recent_errors(self) -> list[dict]:
        with self._lock:
            return [sample.to_dict() for sample in list(self._errors)[-20:]]

    def dataset_status(self) -> dict:
        with self._lock:
            failures = list(self._dataset_failures)
        return {"status": "degraded" if failures else "ok", "recent_failures": failures[-20:]}

    def storage_usage(self, paths: dict[str, str]) -> dict:
        return {
            key: self._directory_usage(path)
            for key, path in paths.items()
            if key in {"datasets", "models", "uploads", "rasters", "cache", "reports", "data_archive", "data_checkpoints"}
        }

    def trace_context(self, request_id: str, operation: str) -> dict:
        return {
            "trace_id": request_id,
            "span_id": f"{operation}:{int(time.time() * 1000)}",
            "operation": operation,
            "recorded_at": self._now(),
        }

    def _append(self, collection: deque[MetricSample], sample: MetricSample) -> None:
        with self._lock:
            collection.append(sample)

    def _latency_summary(self, samples: list[MetricSample]) -> dict:
        values = sorted(sample.value for sample in samples)
        if not values:
            return {"count": 0, "average": None, "p95": None, "max": None}
        p95_index = min(len(values) - 1, int(len(values) * 0.95))
        return {"count": len(values), "average": round(sum(values) / len(values), 4), "p95": values[p95_index], "max": values[-1]}

    def _memory_usage(self) -> dict:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {"max_rss": usage, "unit": "kb_on_linux_bytes_on_macos"}

    def _cpu_usage(self) -> dict:
        load_average = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
        return {"load_average_1m": load_average, "unit": "system_load"}

    def _directory_usage(self, path: str) -> dict:
        total_bytes = 0
        file_count = 0
        root = os.path.abspath(path)
        if not os.path.exists(root):
            return {"status": "missing", "path": path, "bytes": 0, "files": 0}
        for directory, _, files in os.walk(root):
            for filename in files:
                file_path = os.path.join(directory, filename)
                try:
                    total_bytes += os.path.getsize(file_path)
                    file_count += 1
                except OSError:
                    continue
        return {"status": "ok", "path": path, "bytes": total_bytes, "files": file_count}

    def _alert(self, code: str, severity: str, message: str) -> dict:
        return {"code": code, "severity": severity, "message": message, "generated_at": self._now()}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


observability_registry = ObservabilityRegistry()


def time_operation(name: str, recorder: Callable[[float], None]) -> Callable:
    def decorator(function: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                recorder((time.perf_counter() - started) * 1000)

        wrapper.__name__ = getattr(function, "__name__", name)
        return wrapper

    return decorator


class HealthCheckService:
    """Component-level health checks for liveness, readiness, and dashboards."""

    def backend(self) -> dict:
        return {"component": "backend", "status": "ok", "detail": "FastAPI process is running"}

    def database(self) -> dict:
        try:
            from sqlalchemy import text

            from backend.database.session import engine

            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            return {"component": "database", "status": "degraded", "detail": "Database connection check failed"}
        return {"component": "database", "status": "ok", "detail": "Database connection check passed"}

    def cache(self) -> dict:
        try:
            from backend.database.redis import redis_health

            cache_health = redis_health()
        except Exception:
            return {"component": "cache", "status": "degraded", "detail": "Cache health check failed"}
        return {"component": "cache", "status": cache_health["status"], "detail": cache_health}

    def weather_api(self) -> dict:
        try:
            from backend.core.config import get_settings

            settings = get_settings()
            configured = bool(settings.weather_api_base_url)
        except Exception:
            configured = False
        return {"component": "weather_api", "status": "configured" if configured else "missing", "detail": "Weather provider adapter is ready for configured API base URL"}

    def satellite_pipeline(self) -> dict:
        try:
            from backend.services.satellite_processor import SatelliteProcessor

            plan = SatelliteProcessor().preprocessing_plan()
            status = "ok" if plan["dataset_validation"]["valid"] else "degraded"
            return {"component": "satellite_pipeline", "status": status, "detail": plan["performance"]}
        except Exception as exc:
            return {"component": "satellite_pipeline", "status": "degraded", "detail": exc.__class__.__name__}

    def prediction_engine(self) -> dict:
        try:
            from backend.ml.pipeline import FireRiskModelService

            prediction = FireRiskModelService().predict({"temperature": 34, "humidity": 40, "wind_speed": 12, "rainfall": 1, "ndvi": 0.5, "nbr": 0.4, "hotspots": 1})
            return {"component": "prediction_engine", "status": "ok", "detail": {"risk": prediction.risk_category, "confidence": prediction.confidence}}
        except Exception as exc:
            return {"component": "prediction_engine", "status": "degraded", "detail": exc.__class__.__name__}

    def gis_engine(self) -> dict:
        try:
            from backend.services.gis_service import GISService

            stats = GISService().spatial_statistics()
            return {"component": "gis_engine", "status": "ok", "detail": {"regions": stats.get("total_regions")}}
        except Exception as exc:
            return {"component": "gis_engine", "status": "degraded", "detail": exc.__class__.__name__}

    def all_components(self) -> dict:
        checks = [
            self.backend(),
            self.database(),
            self.cache(),
            self.weather_api(),
            self.satellite_pipeline(),
            self.prediction_engine(),
            self.gis_engine(),
        ]
        overall = "ok" if all(check["status"] in {"ok", "configured"} for check in checks) else "degraded"
        return {"overall_status": overall, "components": {check["component"]: check for check in checks}}
