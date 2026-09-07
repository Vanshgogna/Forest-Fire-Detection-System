from fastapi import APIRouter

from backend.core.config import get_settings
from backend.services.environmental_foundation import DataMode
from backend.services.gis_service import GISService
from backend.services.mock_environment import REGIONS

router = APIRouter()
service = GISService()


@router.get("/regions")
def get_regions():
    return {
        "regions": REGIONS,
        "source": {
            "status": "configured",
            "source_type": "configured_region_registry",
            "coordinate_method": "configured representative point",
        },
    }


@router.get("/layers")
def get_layers():
    settings = get_settings()
    hotspot_status = "simulated" if settings.data_mode == DataMode.SIMULATION.value else ("configured" if settings.firms_enabled else "unavailable")
    return {
        "layers": [
            {"id": "risk-heatmap", "name": "Risk Heatmap", "status": "ready"},
            {"id": "ndvi", "name": "NDVI Vegetation Layer", "status": "simulated"},
            {"id": "hotspots", "name": "FIRMS Active Fire Detection Layer", "status": hotspot_status, "provider": "NASA FIRMS"},
            {"id": "weather", "name": "Weather Overlay", "status": "live"},
            {"id": "boundaries", "name": "Forest Boundaries", "status": "ready"},
        ],
        "message": "Weather is live via Open-Meteo. NDVI remains simulated; hotspot markers use FIRMS-ingested database records when configured.",
    }


@router.get("/risk-geojson")
def get_risk_geojson():
    return service.risk_geojson()


@router.get("/heatmap")
def get_heatmap():
    return service.heatmap()


@router.get("/search")
def search_regions(query: str = "", min_risk: int = 0):
    return service.search_regions(query=query, min_risk=min_risk)


@router.get("/spatial-statistics")
def get_spatial_statistics():
    return service.spatial_statistics()


@router.get("/cache-manifest/{layer}")
def get_layer_cache_manifest(layer: str, scene_id: str = "regional-risk"):
    return service.layer_cache_manifest(layer=layer, scene_id=scene_id)
