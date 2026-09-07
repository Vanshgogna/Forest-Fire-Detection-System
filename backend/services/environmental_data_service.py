from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.core.config import Settings, get_settings
from backend.database.session import SessionLocal
from backend.repositories.environment import VegetationRepository
from backend.schemas.environmental import CanonicalHotspotData, CanonicalVegetationData, CanonicalWeatherData, EnvironmentalSnapshot, MissingEnvironmentalData
from backend.services.environmental_foundation import DataMode, DataProvenance, DataQualityStatus, ProviderName, ProviderType
from backend.services.hotspot_aggregation_service import HotspotAggregationService
from backend.services.region_registry import get_region_location
from backend.services.sentinel_acquisition_service import SentinelAcquisitionService
from backend.services.weather_provider import OpenMeteoWeatherProvider


class EnvironmentalDataService:
    """Domain service for canonical environmental data access by region."""

    def __init__(self, weather_provider: OpenMeteoWeatherProvider | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider()

    def get_latest_weather(self, region_id: str) -> CanonicalWeatherData | MissingEnvironmentalData:
        if self.settings.data_mode == DataMode.SIMULATION.value:
            return self._missing("Weather is disabled in simulation mode for canonical snapshots.", DataQualityStatus.SIMULATED)

        weather = self.weather_provider.weather_for_region(region_id=region_id)
        current = weather.get("current") or {}
        if weather.get("status") != "ok" or not current:
            return self._missing(weather.get("message", "Weather provider is unavailable."), DataQualityStatus.UNAVAILABLE)

        return self._canonical_weather_from_payload(weather)

    def get_latest_vegetation(self, region_id: str) -> CanonicalVegetationData | MissingEnvironmentalData:
        if self.settings.data_mode == DataMode.SIMULATION.value:
            return self._missing(f"Vegetation values are simulated fixtures in DATA_MODE=simulation for {region_id}.", DataQualityStatus.SIMULATED)
        try:
            region = get_region_location(region_id)
            with SessionLocal() as db:
                record = VegetationRepository(db).latest_for_region(region.database_id)
                if record and record.provider == ProviderName.SENTINEL_2.value and record.processing_version == self.settings.sentinel_ndvi_processing_version:
                    return self._canonical_vegetation_from_record(record)
                scene = SentinelAcquisitionService(db, settings=self.settings).latest_scene_status(region_id)
            if scene.get("available"):
                return self._missing(
                    f"Sentinel-2 scene {scene.get('scene_id')} is acquired; NDVI processing is not ready.",
                    DataQualityStatus.UNAVAILABLE,
                )
        except Exception:
            pass
        return self._missing(f"Vegetation provider ingestion is not configured for {region_id}.", DataQualityStatus.UNAVAILABLE)

    def get_recent_hotspots(self, region_id: str) -> CanonicalHotspotData | MissingEnvironmentalData:
        if self.settings.data_mode == DataMode.SIMULATION.value:
            return self._missing("Simulation mode is explicit; live FIRMS hotspots are not used.", DataQualityStatus.SIMULATED)
        try:
            with SessionLocal() as db:
                summary = HotspotAggregationService(db, settings=self.settings).summary_for_region(region_id)
                return HotspotAggregationService(db, settings=self.settings).to_canonical_data(summary)
        except Exception as exc:
            return self._missing(f"Hotspot database aggregation is unavailable: {exc.__class__.__name__}.", DataQualityStatus.UNAVAILABLE)

    def get_environmental_snapshot(self, region_id: str) -> EnvironmentalSnapshot:
        region = get_region_location(region_id).as_dict()
        if self.settings.data_mode == DataMode.SIMULATION.value:
            vegetation = self.get_latest_vegetation(region_id)
            hotspots = self.get_recent_hotspots(region_id)
            weather = self._missing("Weather is disabled in simulation mode for canonical snapshots.", DataQualityStatus.SIMULATED)
            return EnvironmentalSnapshot(
                region_id=region_id,
                timestamp=datetime.now(timezone.utc),
                data_mode=self.settings.data_mode,
                region=region,
                weather=weather,
                vegetation=vegetation,
                hotspots=hotspots,
                provenance={
                    "weather": self._unavailable_provenance(region_id, ProviderName.OPEN_METEO.value, ProviderType.WEATHER, DataQualityStatus.SIMULATED).to_dict(),
                    "vegetation": self._vegetation_provenance(region_id, vegetation),
                    "hotspots": self._unavailable_provenance(region_id, ProviderName.NASA_FIRMS.value, ProviderType.HOTSPOT).to_dict(),
                },
                quality={
                    "overall_status": DataQualityStatus.SIMULATED,
                    "weather_status": DataQualityStatus.SIMULATED,
                    "vegetation_status": DataQualityStatus(vegetation.status),
                    "hotspot_status": DataQualityStatus(hotspots.status),
                },
                availability={
                    "weather_available": False,
                    "vegetation_available": getattr(vegetation, "available", False),
                    "hotspots_available": False,
                },
            )

        weather_payload = self.weather_provider.weather_for_region(region_id=region_id)
        current = weather_payload.get("current") or {}
        weather_available = weather_payload.get("status") == "ok" and bool(current)
        weather_status = DataQualityStatus(weather_payload.get("data_status", DataQualityStatus.UNAVAILABLE.value))
        vegetation = self.get_latest_vegetation(region_id)
        hotspots = self.get_recent_hotspots(region_id)

        weather: CanonicalWeatherData | MissingEnvironmentalData
        if weather_available:
            weather = self._canonical_weather_from_payload(weather_payload)
            weather_provenance = weather_payload.get("provenance")
        else:
            weather = self._missing(weather_payload.get("message", "Weather provider is unavailable."), DataQualityStatus.UNAVAILABLE)
            weather_provenance = weather_payload.get("provenance")

        quality = {
            "overall_status": self._overall_status([weather_status, DataQualityStatus(vegetation.status), DataQualityStatus(hotspots.status)]),
            "weather_status": weather_status,
            "vegetation_status": DataQualityStatus(vegetation.status),
            "hotspot_status": DataQualityStatus(hotspots.status),
        }

        return EnvironmentalSnapshot(
            region_id=region_id,
            timestamp=datetime.now(timezone.utc),
            data_mode=self.settings.data_mode,
            region=region,
            weather=weather,
            vegetation=vegetation,
            hotspots=hotspots,
            provenance={
                "weather": weather_provenance,
                "vegetation": self._vegetation_provenance(region_id, vegetation),
                "hotspots": self._hotspot_provenance(region_id, hotspots),
            },
            quality=quality,
            availability={
                "weather_available": weather_available,
                "vegetation_available": getattr(vegetation, "available", False),
                "hotspots_available": getattr(hotspots, "available", False),
            },
        )

    def _missing(self, reason: str, status: DataQualityStatus) -> MissingEnvironmentalData:
        return MissingEnvironmentalData(status=status, reason=reason)

    def _canonical_weather_from_payload(self, weather: dict[str, Any]) -> CanonicalWeatherData:
        current = weather["current"]
        provenance = weather.get("provenance") or {}
        return CanonicalWeatherData(
            temperature=current["temperature"],
            humidity=current["humidity"],
            wind_speed=current["wind_speed"],
            precipitation=current["precipitation"],
            fire_weather_index=current["fire_weather_risk_index"],
            observed_at=provenance.get("observed_at") or current["observed_at"],
            retrieved_at=provenance.get("retrieved_at") or weather["retrieved_at"],
            units=weather["units"],
        )

    def _canonical_vegetation_from_record(self, record) -> CanonicalVegetationData:
        provenance = record.provenance_metadata or {}
        statistics = provenance.get("statistics") or {}
        nbr_statistics = provenance.get("nbr_statistics") or {}
        return CanonicalVegetationData(
            status=DataQualityStatus(record.quality_status),
            provider=record.provider,
            source_type=record.source_type,
            ndvi_mean=record.ndvi,
            ndvi_median=statistics.get("median"),
            ndvi_min=statistics.get("min"),
            ndvi_max=statistics.get("max"),
            nbr_mean=record.nbr,
            nbr_median=nbr_statistics.get("median"),
            nbr_min=nbr_statistics.get("min"),
            nbr_max=nbr_statistics.get("max"),
            nbr_valid_pixel_percentage=nbr_statistics.get("valid_pixel_percentage"),
            valid_pixel_percentage=record.valid_pixel_percentage,
            captured_at=record.captured_at.isoformat(),
            processed_at=record.processed_at.isoformat() if record.processed_at else None,
            scene_id=record.scene_id,
            product_id=record.product_id,
            values={
                "ndvi": record.ndvi,
                "ndvi_mean": record.ndvi,
                "ndvi_median": statistics.get("median"),
                "valid_pixel_percentage": record.valid_pixel_percentage,
                "nbr": record.nbr,
                "nbr_mean": record.nbr,
                "nbr_median": nbr_statistics.get("median"),
                "nbr_valid_pixel_percentage": nbr_statistics.get("valid_pixel_percentage"),
            },
        )

    def _unavailable_provenance(
        self,
        region_id: str,
        provider: str,
        provider_type: ProviderType,
        status: DataQualityStatus = DataQualityStatus.UNAVAILABLE,
    ) -> DataProvenance:
        return DataProvenance(
            provider=provider,
            provider_type=provider_type,
            source_type="not_configured",
            retrieved_at=datetime.now(timezone.utc),
            region_id=region_id,
            quality_status=status,
        )

    def _hotspot_provenance(self, region_id: str, hotspots: CanonicalHotspotData | MissingEnvironmentalData) -> dict[str, Any]:
        if isinstance(hotspots, MissingEnvironmentalData):
            return self._unavailable_provenance(region_id, ProviderName.NASA_FIRMS.value, ProviderType.HOTSPOT, DataQualityStatus(hotspots.status)).to_dict()
        return DataProvenance(
            provider=hotspots.provider,
            provider_type=ProviderType.HOTSPOT,
            source_type=hotspots.source_type,
            retrieved_at=datetime.fromisoformat(hotspots.retrieved_at) if hotspots.retrieved_at else datetime.now(timezone.utc),
            observed_at=datetime.fromisoformat(hotspots.latest_detection_at) if hotspots.latest_detection_at else None,
            acquired_at=datetime.fromisoformat(hotspots.latest_detection_at) if hotspots.latest_detection_at else None,
            region_id=region_id,
            quality_status=DataQualityStatus(hotspots.status),
        ).to_dict()

    def _vegetation_provenance(self, region_id: str, vegetation: CanonicalVegetationData | MissingEnvironmentalData) -> dict[str, Any]:
        if isinstance(vegetation, CanonicalVegetationData):
            captured_at = datetime.fromisoformat(vegetation.captured_at)
            processed_at = datetime.fromisoformat(vegetation.processed_at) if vegetation.processed_at else datetime.now(timezone.utc)
            return DataProvenance(
                provider=vegetation.provider,
                provider_type=ProviderType.SATELLITE,
                source_type=vegetation.source_type,
                source_record_id=vegetation.product_id,
                observed_at=captured_at,
                acquired_at=captured_at,
                retrieved_at=processed_at,
                region_id=region_id,
                quality_status=DataQualityStatus(vegetation.status),
            ).to_dict()
        status = DataQualityStatus(vegetation.status)
        try:
            with SessionLocal() as db:
                scene = SentinelAcquisitionService(db, settings=self.settings).latest_scene_status(region_id)
            if scene.get("product_id"):
                retrieved_at = datetime.fromisoformat(scene["retrieved_at"]) if scene.get("retrieved_at") else datetime.now(timezone.utc)
                observed_at = datetime.fromisoformat(scene["captured_at"]) if scene.get("captured_at") else None
                return DataProvenance(
                    provider=ProviderName.SENTINEL_2.value,
                    provider_type=ProviderType.SATELLITE,
                    source_type=scene.get("source_type") or "copernicus_odata_products",
                    source_record_id=scene.get("product_id"),
                    observed_at=observed_at,
                    acquired_at=observed_at,
                    retrieved_at=retrieved_at,
                    region_id=region_id,
                    quality_status=status,
                ).to_dict()
        except Exception:
            pass
        return self._unavailable_provenance(region_id, ProviderName.SENTINEL_2.value, ProviderType.SATELLITE, status).to_dict()

    def _overall_status(self, statuses: list[DataQualityStatus]) -> DataQualityStatus:
        if all(status == DataQualityStatus.UNAVAILABLE for status in statuses):
            return DataQualityStatus.UNAVAILABLE
        if any(status == DataQualityStatus.SUSPICIOUS for status in statuses):
            return DataQualityStatus.SUSPICIOUS
        if any(status == DataQualityStatus.STALE for status in statuses):
            return DataQualityStatus.STALE
        if any(status == DataQualityStatus.UNAVAILABLE for status in statuses):
            return DataQualityStatus.UNAVAILABLE
        if any(status == DataQualityStatus.CACHED for status in statuses):
            return DataQualityStatus.CACHED
        if any(status == DataQualityStatus.RECENT for status in statuses):
            return DataQualityStatus.RECENT
        if any(status == DataQualityStatus.SIMULATED for status in statuses):
            return DataQualityStatus.SIMULATED
        return DataQualityStatus.LIVE
