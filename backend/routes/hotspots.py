from fastapi import APIRouter, Depends, HTTPException

from backend.core.config import get_settings
from backend.core.security import Principal, require_researcher
from backend.database.session import SessionLocal
from backend.services.environmental_foundation import DataMode
from backend.services.hotspot_aggregation_service import HotspotAggregationService
from backend.services.hotspot_ingestion_service import FIRMSIngestionService
from backend.services.mock_environment import REGIONS
from backend.services.region_registry import get_region_location

router = APIRouter()


@router.get("/")
def list_hotspots():
    settings = get_settings()
    if settings.data_mode == DataMode.SIMULATION.value:
        hotspots = [
            {
                "region_id": region.id,
                "region": region.name,
                "count_24h": region.hotspots,
                "count": region.hotspots,
                "severity": region.risk_level,
                "source": "development fixture",
                "source_type": "simulated_development_fixture",
                "status": "SIMULATED",
                "detections": [],
            }
            for region in REGIONS
        ]
        return {
            "hotspots": hotspots,
            "total": sum(region.hotspots for region in REGIONS),
            "status": "SIMULATED",
            "provider": "development-fixture",
            "message": "DATA_MODE=simulation is explicit; hotspot counts are development fixtures.",
        }

    try:
        with SessionLocal() as db:
            summaries = HotspotAggregationService(db, settings=settings).summaries()
    except Exception as exc:
        return _unavailable(f"Hotspot database aggregation is unavailable: {exc.__class__.__name__}.")

    response_items = [_summary_payload(summary) for summary in summaries]
    available = [item for item in response_items if item["available"]]
    if not available:
        message = response_items[0]["message"] if response_items else "Hotspot data unavailable."
        return _unavailable(message, response_items)
    return {
        "hotspots": response_items,
        "total": sum(item["count_24h"] for item in available),
        "status": _worst_status([item["status"] for item in available]),
        "provider": "nasa-firms",
        "source_type": "firms_area_csv",
        "attribution": "NASA FIRMS",
        "message": "NASA FIRMS active-fire detections from database-backed ingestion.",
    }


@router.get("/{region_id}")
def hotspots_for_region(region_id: str):
    try:
        get_region_location(region_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    settings = get_settings()
    try:
        with SessionLocal() as db:
            summary = HotspotAggregationService(db, settings=settings).summary_for_region(region_id)
        return _summary_payload(summary)
    except Exception as exc:
        return {
            "region_id": region_id,
            "available": False,
            "provider": "nasa-firms",
            "product": settings.firms_product,
            "source_type": "firms_area_csv",
            "status": "UNAVAILABLE",
            "count_24h": None,
            "count_48h": None,
            "count_7d": None,
            "count": None,
            "nearest_hotspot_distance_km": None,
            "latest_detection_at": None,
            "retrieved_at": None,
            "detections": [],
            "message": f"Hotspot database aggregation is unavailable: {exc.__class__.__name__}.",
            "attribution": "NASA FIRMS",
        }


@router.post("/ingest")
def ingest_hotspots(region_id: str | None = None, _: Principal = Depends(require_researcher)):
    region_ids = [region_id] if region_id else None
    try:
        if region_id:
            get_region_location(region_id)
        with SessionLocal() as db:
            result = FIRMSIngestionService(db).ingest_regions(region_ids)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _summary_payload(summary):
    return {
        "region_id": summary.region_id,
        "available": summary.available,
        "provider": summary.provider,
        "product": summary.product,
        "source_type": summary.source_type,
        "status": summary.status.value,
        "count_24h": summary.count_24h,
        "count_48h": summary.count_48h,
        "count_7d": summary.count_7d,
        "count": summary.count_24h,
        "nearest_hotspot_distance_km": summary.nearest_hotspot_distance_km,
        "latest_detection_at": summary.latest_detection_at.isoformat() if summary.latest_detection_at else None,
        "retrieved_at": summary.retrieved_at.isoformat() if summary.retrieved_at else None,
        "detections": [record.model_dump() for record in summary.records],
        "message": summary.message,
        "attribution": "NASA FIRMS" if summary.provider == "nasa-firms" else None,
    }


def _unavailable(message: str, items: list[dict] | None = None):
    return {
        "hotspots": items or [],
        "total": None,
        "status": "UNAVAILABLE",
        "provider": "nasa-firms",
        "source_type": "firms_area_csv",
        "message": message,
        "attribution": "NASA FIRMS",
    }


def _worst_status(statuses: list[str]) -> str:
    order = ["UNAVAILABLE", "SUSPICIOUS", "STALE", "CACHED", "RECENT", "LIVE"]
    return min(statuses, key=lambda status: order.index(status) if status in order else 0)
