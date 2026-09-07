from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.config import get_settings
from backend.core.security import Principal, require_admin
from backend.services.observability import HealthCheckService, observability_registry

router = APIRouter()
health = HealthCheckService()


@router.get("/health")
def component_health():
    return health.all_components()


@router.get("/health/backend")
def backend_health():
    return health.backend()


@router.get("/health/database")
def database_health():
    return health.database()


@router.get("/health/cache")
def cache_health():
    return health.cache()


@router.get("/health/weather-api")
def weather_api_health():
    return health.weather_api()


@router.get("/health/satellite-pipeline")
def satellite_pipeline_health():
    return health.satellite_pipeline()


@router.get("/health/prediction-engine")
def prediction_engine_health():
    return health.prediction_engine()


@router.get("/health/gis-engine")
def gis_engine_health():
    return health.gis_engine()


@router.get("/metrics")
def application_metrics(_: Principal = Depends(require_admin)):
    return observability_registry.application_metrics()


@router.get("/model")
def model_monitoring(_: Principal = Depends(require_admin)):
    return observability_registry.model_monitoring()


@router.get("/alerts")
def monitoring_alerts(_: Principal = Depends(require_admin)):
    return {"alerts": observability_registry.monitoring_alerts()}


@router.get("/dashboard")
def observability_dashboard(_: Principal = Depends(require_admin)):
    settings = get_settings()
    health_summary = health.all_components()
    metrics = observability_registry.application_metrics()
    model = observability_registry.model_monitoring()
    dataset_status = observability_registry.dataset_status()
    storage = observability_registry.storage_usage(settings.artifact_directories())
    alerts = observability_registry.monitoring_alerts()
    recent_errors = observability_registry.recent_errors()
    overall = "healthy"
    if alerts or health_summary["overall_status"] != "ok" or dataset_status["status"] != "ok":
        overall = "attention_required"
    return {
        "overall_platform_health": overall,
        "system_health": health_summary,
        "api_performance": {
            "response_time_ms": metrics["api_response_time_ms"],
            "request_count": metrics["request_count"],
            "error_rate": metrics["error_rate"],
        },
        "model_performance": model,
        "dataset_status": dataset_status,
        "storage_usage": storage,
        "recent_errors": recent_errors,
        "alerts": alerts,
        "metrics": metrics,
    }
