import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.core.config import get_settings
from backend.core.security import Principal, require_researcher
from backend.database.session import SessionLocal
from backend.schemas.domain import SatelliteMetadata, SatelliteScenePlanRequest, VegetationIndexRequest
from backend.services.environmental_foundation import DataMode, DataQualityStatus, ProviderName
from backend.services.sentinel_acquisition_service import SentinelAcquisitionService
from backend.services.sentinel_ndvi_service import SentinelNDVIService
from backend.services.sentinel_quality_mask_service import SentinelQualityMaskService
from backend.services.sentinel_raster_service import SentinelRasterService
from backend.services.mock_environment import REGIONS
from backend.services.region_registry import get_region_location, list_region_locations
from backend.services.satellite_processor import SatelliteProcessor

router = APIRouter()
processor = SatelliteProcessor()
logger = logging.getLogger("firesight.sentinel")
FIXTURE_SOURCE = {
    "status": "simulated",
    "source_type": "simulated_development_fixture",
    "message": "Live Sentinel-2 vegetation data is not configured; values are development fixtures.",
}


@router.get("/summary")
def vegetation_summary():
    settings = get_settings()
    if settings.data_mode != DataMode.SIMULATION.value:
        ndvi_regions = []
        try:
            with SessionLocal() as db:
                ndvi_service = SentinelNDVIService(db)
                ndvi_regions = [ndvi_service.ndvi_status(region.id) for region in list_region_locations()]
        except Exception:
            ndvi_regions = []
        ready_ndvi = [item for item in ndvi_regions if item.get("available") and isinstance(item.get("mean"), (int, float))]
        return {
            "average_ndvi": round(sum(float(item["mean"]) for item in ready_ndvi) / len(ready_ndvi), 4) if ready_ndvi else None,
            "average_nbr": None,
            "dry_vegetation_percent": None,
            "satellite_source": "Sentinel-2 L2A NDVI" if ready_ndvi else "Sentinel-2 acquisition only",
            "source": {
                "status": "live" if ready_ndvi else "unavailable",
                "source_type": "sentinel2_l2a_ndvi_processing" if ready_ndvi else "copernicus_odata_products",
                "provider": ProviderName.SENTINEL_2.value,
                "data_status": DataQualityStatus.LIVE.value if ready_ndvi else DataQualityStatus.UNAVAILABLE.value,
                "message": "Sentinel-2 NDVI summary is derived from processed B04/B08 rasters." if ready_ndvi else "Sentinel-2 NDVI processing is available separately; NBR processing is not implemented.",
            },
            "regions": [_ndvi_region_summary(region, ndvi_regions) for region in REGIONS],
        }
    return {
        "average_ndvi": round(sum(region.ndvi for region in REGIONS) / len(REGIONS), 2),
        "average_nbr": round(sum(region.nbr for region in REGIONS) / len(REGIONS), 2),
        "dry_vegetation_percent": 42,
        "satellite_source": "development fixture",
        "source": FIXTURE_SOURCE,
        "regions": [{"region": region.name, "ndvi": region.ndvi, "nbr": region.nbr, "source_type": "simulated_development_fixture"} for region in REGIONS],
    }


@router.post("/indices")
def calculate_indices(payload: VegetationIndexRequest):
    ndvi = processor.calculate_ndvi(payload.nir, payload.red)
    nbr = processor.calculate_nbr(payload.nir, payload.swir)
    return {"ndvi": ndvi, "nbr": nbr, "vegetation_health_index": processor.vegetation_health_index(ndvi, nbr, payload.cloud_percentage)}


@router.post("/satellite/preprocess")
def satellite_preprocessing_plan(payload: SatelliteMetadata):
    return {**processor.preprocessing_plan(payload.source), "metadata": payload.model_dump()}


@router.get("/satellite/tiles/{scene_id}")
def satellite_tile_manifest(scene_id: str):
    return processor.tile_manifest(scene_id)


@router.post("/satellite/scene-plan")
def satellite_scene_plan(payload: SatelliteScenePlanRequest):
    return processor.full_scene_plan(payload.model_dump())


@router.get("/satellite/cleanup/{scene_id}")
def satellite_cleanup_plan(scene_id: str):
    return processor.pipeline.cleanup_plan(scene_id)


@router.get("/satellite/latest")
def latest_sentinel_scene(region_id: str = "r1"):
    try:
        get_region_location(region_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        with SessionLocal() as db:
            return SentinelAcquisitionService(db).latest_scene_status(region_id)
    except Exception as exc:
        return _unavailable_satellite_status(region_id, f"Sentinel scene metadata is unavailable: {exc.__class__.__name__}.")


@router.get("/satellite/status")
def sentinel_scene_status():
    settings = get_settings()
    try:
        with SessionLocal() as db:
            service = SentinelAcquisitionService(db, settings=settings)
            ndvi_service = SentinelNDVIService(db, settings=settings)
            scenes = []
            for region in list_region_locations():
                scene = service.latest_scene_status(region.id)
                if _needs_ndvi_nbr_processing(scene) and settings.sentinel_enabled:
                    logger.info(
                        "sentinel_ndvi_nbr_calculation_started region_id=%s reason=%s",
                        region.id,
                        _sentinel_processing_reason(scene),
                    )
                    result = ndvi_service.calculate_ndvi(region.id)
                    logger.info(
                        "sentinel_ndvi_nbr_calculation_completed region_id=%s status=%s quality_status=%s error_kind=%s error_message=%s",
                        region.id,
                        result.status,
                        result.quality_status.value,
                        result.error.kind.value if result.error else None,
                        result.error.message if result.error else None,
                    )
                    scene = service.latest_scene_status(region.id)
                scenes.append(scene)
        available = [scene for scene in scenes if scene["available"]]
        return {
            "scenes": scenes,
            "total": len(scenes),
            "available": len(available),
            "status": _worst_status([scene["status"] for scene in scenes]),
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": "copernicus_odata_products",
            "message": "Sentinel-2 acquisition and NDVI/NBR processing status.",
            "attribution": "Copernicus Data Space Ecosystem",
        }
    except Exception as exc:
        return {
            "scenes": [_unavailable_satellite_status(region.id, f"Sentinel scene metadata is unavailable: {exc.__class__.__name__}.") for region in list_region_locations()],
            "total": len(list_region_locations()),
            "available": 0,
            "status": DataQualityStatus.UNAVAILABLE.value,
            "provider": ProviderName.SENTINEL_2.value,
            "source_type": "copernicus_odata_products",
            "message": f"Sentinel scene metadata is unavailable: {exc.__class__.__name__}.",
            "attribution": "Copernicus Data Space Ecosystem",
        }


@router.post("/satellite/acquire")
def acquire_sentinel_scene(region_id: str | None = None, _: Principal = Depends(require_researcher)):
    region_ids = [region_id] if region_id else None
    try:
        if region_id:
            get_region_location(region_id)
        with SessionLocal() as db:
            return SentinelAcquisitionService(db).acquire_latest_scene(region_ids).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/satellite/processing-status")
def sentinel_raster_processing_status(region_id: str = "r1", scene_id: str | None = None):
    try:
        get_region_location(region_id)
        with SessionLocal() as db:
            return SentinelRasterService(db).processing_status(region_id, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/satellite/quality-status")
def sentinel_quality_mask_status(region_id: str = "r1", scene_id: str | None = None):
    try:
        get_region_location(region_id)
        with SessionLocal() as db:
            return SentinelQualityMaskService(db).quality_status(region_id, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/satellite/ndvi-status")
def sentinel_ndvi_status(region_id: str = "r1", scene_id: str | None = None):
    try:
        get_region_location(region_id)
        with SessionLocal() as db:
            return SentinelNDVIService(db).ndvi_status(region_id, scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _unavailable_satellite_status(region_id: str, message: str):
    return {
        "region_id": region_id,
        "available": False,
        "provider": ProviderName.SENTINEL_2.value,
        "source_type": "copernicus_odata_products",
        "status": DataQualityStatus.UNAVAILABLE.value,
        "acquisition_status": "UNAVAILABLE",
        "product_id": None,
        "scene_id": None,
        "platform": None,
        "product_level": None,
        "captured_at": None,
        "retrieved_at": None,
        "cloud_percentage": None,
        "tile_id": None,
        "storage_available": False,
        "file_size_bytes": None,
        "checksum": None,
        "message": message,
        "attribution": "Copernicus Data Space Ecosystem",
    }


def _ndvi_region_summary(region, ndvi_regions: list[dict]):
    item = next((entry for entry in ndvi_regions if entry.get("region_id") == region.id), {})
    ready = item.get("available") and isinstance(item.get("mean"), (int, float)) and isinstance(item.get("nbr_mean"), (int, float))
    return {
        "region_id": region.id,
        "region": region.name,
        "ndvi": item.get("mean") if ready else None,
        "nbr": item.get("nbr_mean") if ready else None,
        "source_type": "sentinel2_l2a_ndvi_processing" if ready else "copernicus_odata_products",
        "status": item.get("quality_status", DataQualityStatus.UNAVAILABLE.value),
        "valid_pixel_percentage": item.get("valid_pixel_percentage"),
    }


def _worst_status(statuses: list[str]) -> str:
    order = ["UNAVAILABLE", "SUSPICIOUS", "STALE", "CACHED", "RECENT", "LIVE"]
    return min(statuses, key=lambda status: order.index(status) if status in order else 0) if statuses else DataQualityStatus.UNAVAILABLE.value


def _needs_ndvi_nbr_processing(scene: dict) -> bool:
    ndvi = scene.get("ndvi_processing") or {}
    if ndvi.get("status") not in {"READY", "LOW_QUALITY"}:
        return True
    return not (isinstance(ndvi.get("mean"), (int, float)) and isinstance(ndvi.get("nbr_mean"), (int, float)))


def _sentinel_processing_reason(scene: dict) -> str:
    if not scene.get("available"):
        return "no_acquired_scene"
    ndvi = scene.get("ndvi_processing") or {}
    if ndvi.get("status") not in {"READY", "LOW_QUALITY"}:
        return "ndvi_not_ready"
    if not isinstance(ndvi.get("nbr_mean"), (int, float)):
        return "nbr_missing"
    return "refresh_requested"
