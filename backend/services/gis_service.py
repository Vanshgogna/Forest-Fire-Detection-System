from backend.core.config import get_settings
from backend.database.session import SessionLocal
from backend.services.environmental_foundation import DataMode
from backend.services.hotspot_aggregation_service import HotspotAggregationService
from backend.services.mock_environment import REGIONS
from backend.services.remote_sensing import RemoteSensingPipeline


class GISService:
    def __init__(self):
        self.pipeline = RemoteSensingPipeline()

    def risk_geojson(self) -> dict:
        return self.pipeline.geojson_feature_collection(
            [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [region.coordinates[1], region.coordinates[0]]},
                    "properties": {
                        "id": region.id,
                        "name": region.name,
                        "state": region.state,
                        "risk_score": region.risk_score,
                        "risk_level": region.risk_level,
                        "confidence": region.confidence,
                        "source_type": "simulated_development_fixture",
                    },
                }
                for region in REGIONS
            ]
        )

    def spatial_statistics(self) -> dict:
        settings = get_settings()
        total_hotspots = sum(region.hotspots for region in REGIONS)
        hotspot_source_type = "simulated_development_fixture"
        hotspot_status = "SIMULATED"
        if settings.data_mode != DataMode.SIMULATION.value:
            try:
                with SessionLocal() as db:
                    summaries = HotspotAggregationService(db, settings=settings).summaries()
                available = [summary for summary in summaries if summary.available]
                total_hotspots = sum(summary.count_24h or 0 for summary in available) if available else None
                hotspot_source_type = "firms_area_csv"
                hotspot_status = "LIVE" if available else "UNAVAILABLE"
            except Exception:
                total_hotspots = None
                hotspot_source_type = "firms_area_csv"
                hotspot_status = "UNAVAILABLE"
        return {
            "total_regions": len(REGIONS),
            "total_hotspots": total_hotspots,
            "average_ndvi": round(sum(region.ndvi for region in REGIONS) / len(REGIONS), 2),
            "high_risk_regions": len([region for region in REGIONS if region.risk_score >= 70]),
            "satellite_coverage": 97,
            "hotspot_source_type": hotspot_source_type,
            "hotspot_status": hotspot_status,
            "source_type": "simulated_development_fixture",
        }

    def heatmap(self) -> dict:
        hotspot_counts = self._hotspot_counts()
        return self.pipeline.geojson_feature_collection(
            [
                self.pipeline.heatmap_feature(
                    longitude=region.coordinates[1],
                    latitude=region.coordinates[0],
                    weight=region.risk_score / 100,
                    properties={"risk_level": region.risk_level, "hotspots": hotspot_counts.get(region.id), "hotspot_source_type": hotspot_counts.get("source_type")},
                )
                for region in REGIONS
            ]
        )

    def search_regions(self, query: str = "", min_risk: int = 0) -> dict:
        normalized = query.lower().strip()
        regions = [
            region
            for region in REGIONS
            if region.risk_score >= min_risk and (not normalized or normalized in region.name.lower() or normalized in region.state.lower())
        ]
        return {
            "results": [
                {
                    "id": region.id,
                    "name": region.name,
                    "state": region.state,
                    "coordinates": region.coordinates,
                    "risk_score": region.risk_score,
                    "risk_level": region.risk_level,
                }
                for region in regions
            ],
            "total": len(regions),
        }

    def layer_cache_manifest(self, layer: str, scene_id: str = "regional-risk") -> dict:
        return self.pipeline.tile_cache_manifest(scene_id=scene_id, layer=layer)

    def _hotspot_counts(self) -> dict:
        settings = get_settings()
        if settings.data_mode == DataMode.SIMULATION.value:
            counts = {region.id: region.hotspots for region in REGIONS}
            counts["source_type"] = "simulated_development_fixture"
            return counts
        try:
            with SessionLocal() as db:
                summaries = HotspotAggregationService(db, settings=settings).summaries()
            counts = {summary.region_id: summary.count_24h if summary.available else None for summary in summaries}
            counts["source_type"] = "firms_area_csv"
            return counts
        except Exception:
            counts = {region.id: None for region in REGIONS}
            counts["source_type"] = "firms_area_csv"
            return counts
