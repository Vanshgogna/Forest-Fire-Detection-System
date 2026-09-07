from fastapi import APIRouter, Depends

from backend.core.security import Principal, require_admin
from backend.services.observability import HealthCheckService, observability_registry

router = APIRouter()
health = HealthCheckService()


@router.get("/system-health")
def system_health(_: Principal = Depends(require_admin)):
    component_health = health.all_components()
    return {
        "api": "ok",
        "database": "configured",
        "cache": component_health["components"]["cache"]["detail"],
        "components": component_health["components"],
        "overall_status": component_health["overall_status"],
        "metrics": observability_registry.application_metrics(),
        "alerts": observability_registry.monitoring_alerts(),
        "workers": {"celery": "configured", "scheduler": "configured"},
        "storage": {"uploads": "configured", "cloudinary": "future_adapter"},
    }


@router.get("/audit-summary")
def audit_summary(_: Principal = Depends(require_admin)):
    return {
        "events": [],
        "tracked_resources": ["users", "predictions", "alerts", "reports", "models", "settings"],
        "retention_policy_days": 365,
    }
