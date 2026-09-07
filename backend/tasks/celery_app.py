try:
    from celery import Celery
except Exception:  # pragma: no cover
    Celery = None

from backend.core.config import get_settings

settings = get_settings()
redis_broker_url = settings.redis_connection_url()
celery_app = Celery("firesight", broker=redis_broker_url, backend=redis_broker_url) if Celery and redis_broker_url else None

if celery_app:
    celery_app.conf.beat_schedule = {
        "firesight-ingest-firms-hotspots": {
            "task": "firesight.ingest_firms_hotspots",
            "schedule": max(60, settings.firms_refresh_interval_minutes * 60),
            "options": {"expires": max(120, settings.firms_refresh_interval_minutes * 60)},
        },
        "firesight-acquire-sentinel-scene": {
            "task": "firesight.acquire_latest_sentinel_scene",
            "schedule": max(3600, settings.sentinel_refresh_interval_hours * 3600),
            "options": {"expires": max(7200, settings.sentinel_refresh_interval_hours * 3600)},
        },
    }
