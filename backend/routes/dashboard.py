from fastapi import APIRouter

from backend.services.cache import CacheService
from backend.core.config import get_settings
from backend.database.session import SessionLocal
from backend.services.environmental_foundation import DataMode
from backend.services.hotspot_aggregation_service import HotspotAggregationService
from backend.services.mock_environment import ALERTS, REGIONS
from backend.services.weather_provider import OpenMeteoWeatherProvider

router = APIRouter()
cache = CacheService()
weather_provider = OpenMeteoWeatherProvider(cache=cache)


@router.get("/overview")
def dashboard_overview():
    def build():
        settings = get_settings()
        hotspot_status = "SIMULATED"
        hotspot_source = "development fixture"
        hotspot_source_type = "simulated_development_fixture"
        total_hotspots = sum(region.hotspots for region in REGIONS)
        if settings.data_mode != DataMode.SIMULATION.value:
            try:
                with SessionLocal() as db:
                    summaries = HotspotAggregationService(db, settings=settings).summaries()
                available = [summary for summary in summaries if summary.available]
                total_hotspots = sum(summary.count_24h or 0 for summary in available) if available else None
                hotspot_status = "LIVE" if available else "UNAVAILABLE"
                hotspot_source = "nasa-firms"
                hotspot_source_type = "firms_area_csv"
            except Exception:
                total_hotspots = None
                hotspot_status = "UNAVAILABLE"
                hotspot_source = "nasa-firms"
                hotspot_source_type = "firms_area_csv"
        high_risk = [region for region in REGIONS if region.risk_score >= 70]
        weather = weather_provider.weather_for_region(region_id="r1")
        current_weather = weather.get("current") or {}
        return {
            "risk": {
                "average_score": round(sum(region.risk_score for region in REGIONS) / len(REGIONS)),
                "high_risk_regions": len(high_risk),
                "top_region": max(REGIONS, key=lambda region: region.risk_score).name,
                "source_type": "simulated_development_fixture",
            },
            "weather": {
                "status": weather.get("status"),
                "provider": weather.get("provider"),
                "temperature": current_weather.get("temperature"),
                "fire_weather_risk_index": current_weather.get("fire_weather_risk_index"),
                "forecast_points": len(weather.get("hourly", [])),
                "location": weather.get("location"),
                "retrieved_at": weather.get("retrieved_at"),
                "cache": weather.get("cache"),
            },
            "hotspots": {"active": total_hotspots, "source": hotspot_source, "source_type": hotspot_source_type, "status": hotspot_status, "attribution": "NASA FIRMS" if hotspot_source == "nasa-firms" else None},
            "alerts": {"open": len(ALERTS), "critical": len([alert for alert in ALERTS if alert.severity == "Critical"]), "source_type": "simulated_development_fixture"},
            "cache": "redis_or_fallback",
        }

    return cache.get_or_set("dashboard:overview", build, ttl_seconds=120)


@router.get("/top-risk-regions")
def top_risk_regions(limit: int = 5):
    regions = sorted(REGIONS, key=lambda region: region.risk_score, reverse=True)[:limit]
    return {
        "regions": [
            {
                "id": region.id,
                "name": region.name,
                "state": region.state,
                "risk_score": region.risk_score,
                "risk_level": region.risk_level,
                "confidence": region.confidence,
            }
            for region in regions
        ]
    }
