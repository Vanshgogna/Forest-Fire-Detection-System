from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.core.errors import AppError, app_error_handler, http_exception_handler, unhandled_exception_handler, validation_exception_handler
from backend.core.logging import configure_logging, log_startup_event, request_logging_middleware
from backend.database.redis import close_redis, current_redis_client, init_redis
from backend.middleware.rate_limit import rate_limit_middleware
from backend.middleware.request_security import replay_protection_middleware, request_size_limit_middleware
from backend.middleware.security_headers import security_headers_middleware
from backend.routes import admin, alerts, analytics, auth, dashboard, data, environmental_snapshot, gis, hotspots, monitoring, notifications, prediction, reports, settings, users, vegetation, weather

settings_obj = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging()
    settings_obj.ensure_artifact_directories()
    await init_redis(settings_obj)
    application.state.redis = current_redis_client()
    log_startup_event(
        "application_startup",
        app=settings_obj.app_name,
        version="0.2.0",
        environment=settings_obj.environment,
        api_version=settings_obj.api_version,
    )
    yield
    await close_redis()
    application.state.redis = None
    log_startup_event("application_shutdown", app=settings_obj.app_name, version="0.2.0")


app = FastAPI(
    title=settings_obj.app_name,
    version="0.2.0",
    description="Environmental intelligence API for forest fire risk prediction, GIS analytics, alerts, reports, and explainable AI.",
    lifespan=lifespan,
)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_obj.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(request_size_limit_middleware)
app.middleware("http")(replay_protection_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(data.router, prefix="/api/data", tags=["data-engineering"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
app.include_router(environmental_snapshot.router, prefix="/api/environmental-snapshot", tags=["environmental-snapshot"])
app.include_router(vegetation.router, prefix="/api/vegetation", tags=["vegetation"])
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["hotspots"])
app.include_router(prediction.router, prefix="/api/prediction", tags=["prediction"])
app.include_router(gis.router, prefix="/api/gis", tags=["gis"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

versioned_prefix = f"/api/{settings_obj.api_version}"
app.include_router(auth.router, prefix=f"{versioned_prefix}/auth", tags=["v1-authentication"], include_in_schema=False)
app.include_router(dashboard.router, prefix=f"{versioned_prefix}/dashboard", tags=["v1-dashboard"], include_in_schema=False)
app.include_router(data.router, prefix=f"{versioned_prefix}/data", tags=["v1-data-engineering"], include_in_schema=False)
app.include_router(users.router, prefix=f"{versioned_prefix}/users", tags=["v1-users"], include_in_schema=False)
app.include_router(weather.router, prefix=f"{versioned_prefix}/weather", tags=["v1-weather"], include_in_schema=False)
app.include_router(environmental_snapshot.router, prefix=f"{versioned_prefix}/environmental-snapshot", tags=["v1-environmental-snapshot"], include_in_schema=False)
app.include_router(vegetation.router, prefix=f"{versioned_prefix}/vegetation", tags=["v1-vegetation"], include_in_schema=False)
app.include_router(hotspots.router, prefix=f"{versioned_prefix}/hotspots", tags=["v1-hotspots"], include_in_schema=False)
app.include_router(prediction.router, prefix=f"{versioned_prefix}/prediction", tags=["v1-prediction"], include_in_schema=False)
app.include_router(gis.router, prefix=f"{versioned_prefix}/gis", tags=["v1-gis"], include_in_schema=False)
app.include_router(alerts.router, prefix=f"{versioned_prefix}/alerts", tags=["v1-alerts"], include_in_schema=False)
app.include_router(analytics.router, prefix=f"{versioned_prefix}/analytics", tags=["v1-analytics"], include_in_schema=False)
app.include_router(reports.router, prefix=f"{versioned_prefix}/reports", tags=["v1-reports"], include_in_schema=False)
app.include_router(notifications.router, prefix=f"{versioned_prefix}/notifications", tags=["v1-notifications"], include_in_schema=False)
app.include_router(monitoring.router, prefix=f"{versioned_prefix}/monitoring", tags=["v1-monitoring"], include_in_schema=False)
app.include_router(settings.router, prefix=f"{versioned_prefix}/settings", tags=["v1-settings"], include_in_schema=False)
app.include_router(admin.router, prefix=f"{versioned_prefix}/admin", tags=["v1-admin"], include_in_schema=False)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": settings_obj.app_name, "version": "0.2.0"}


@app.get("/api/readiness")
def readiness_check():
    component_health = monitoring.health.all_components()
    ready = component_health["overall_status"] == "ok"
    return {
        "api": "ready" if ready else "degraded",
        "database": component_health["components"]["database"]["status"],
        "cache": component_health["components"]["cache"]["status"],
        "ml": component_health["components"]["prediction_engine"]["status"],
        "workers": "configured",
        "components": component_health["components"],
        "versioned_api": f"/api/{settings_obj.api_version}",
        "configuration": settings_obj.public_config(),
    }
