from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.database.models import Region, SystemSetting
from backend.repositories.environment import HotspotRepository
from backend.schemas.environmental import CanonicalHotspotData, HotspotDetection, MissingEnvironmentalData
from backend.services.environmental_foundation import DataMode, DataQualityStatus, FreshnessPolicy, ProviderName
from backend.services.region_registry import get_region_location, list_region_locations


@dataclass(frozen=True)
class HotspotSummary:
    status: DataQualityStatus
    available: bool
    region_id: str
    provider: str
    product: str
    retrieved_at: datetime | None
    latest_detection_at: datetime | None
    count_24h: int | None
    count_48h: int | None
    count_7d: int | None
    nearest_hotspot_distance_km: float | None
    records: list[HotspotDetection]
    message: str | None = None
    source_type: str = "firms_area_csv"


class HotspotAggregationService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def summary_for_region(self, region_id: str, limit: int = 100) -> HotspotSummary:
        region = get_region_location(region_id)
        if self.settings.data_mode == DataMode.SIMULATION.value:
            return HotspotSummary(
                status=DataQualityStatus.SIMULATED,
                available=False,
                region_id=region.id,
                provider=ProviderName.DEVELOPMENT_FIXTURE.value,
                product="simulation",
                retrieved_at=datetime.now(timezone.utc),
                latest_detection_at=None,
                count_24h=None,
                count_48h=None,
                count_7d=None,
                nearest_hotspot_distance_km=None,
                records=[],
                message="Simulation mode is explicit; live FIRMS hotspots are not used.",
                source_type="simulated_development_fixture",
            )
        if not self.settings.firms_enabled:
            return self._unavailable(region.id, "FIRMS ingestion is disabled by FIRMS_ENABLED.")

        try:
            region_row = self.db.get(Region, region.database_id) or self.db.query(Region).filter(Region.name == region.name).first()
            last_ingestion = self._last_ingestion(region.id)
            if not region_row:
                if last_ingestion and last_ingestion.get("status") == DataQualityStatus.LIVE.value and last_ingestion.get("records_valid") == 0:
                    return HotspotSummary(
                        status=DataQualityStatus.LIVE,
                        available=True,
                        region_id=region.id,
                        provider=ProviderName.NASA_FIRMS.value,
                        product=last_ingestion.get("product") or self.settings.firms_product,
                        retrieved_at=self._parse_datetime(last_ingestion.get("retrieved_at")),
                        latest_detection_at=None,
                        count_24h=0,
                        count_48h=0,
                        count_7d=0,
                        nearest_hotspot_distance_km=None,
                        records=[],
                        message="NASA FIRMS was queried successfully and returned zero active-fire detections.",
                    )
                return self._unavailable(region.id, "No hotspot database records or successful zero-detection ingestion status exist for this region.")
            hotspot_repo = HotspotRepository(self.db)
            now = datetime.now(timezone.utc)
            count_24h = hotspot_repo.count_since(region_row.id, now - timedelta(hours=24))
            count_48h = hotspot_repo.count_since(region_row.id, now - timedelta(hours=48))
            count_7d = hotspot_repo.count_since(region_row.id, now - timedelta(days=7))
            latest_hotspot = hotspot_repo.latest_for_region(region_row.id)
            latest_retrieved = hotspot_repo.latest_retrieved_for_region(region_row.id)

            if not last_ingestion and not latest_hotspot:
                return self._unavailable(region.id, "No successful FIRMS ingestion has been recorded for this region.")

            retrieved_at = self._parse_datetime(last_ingestion.get("retrieved_at") if last_ingestion else None) or (latest_retrieved.retrieved_at if latest_retrieved else None)
            latest_detection_at = latest_hotspot.detected_at if latest_hotspot else self._parse_datetime(last_ingestion.get("latest_detection_at") if last_ingestion else None)
            if latest_detection_at and latest_detection_at.tzinfo is None:
                latest_detection_at = latest_detection_at.replace(tzinfo=timezone.utc)
            if retrieved_at and retrieved_at.tzinfo is None:
                retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
            status = self._status_from_timestamps(retrieved_at, latest_detection_at, last_ingestion)
            records = [
                self._record_to_schema(record)
                for record in hotspot_repo.recent_for_region(region_row.id, now - timedelta(days=7), limit=limit)
            ]
            nearest = self._nearest_distance(region.latitude, region.longitude, records)
            return HotspotSummary(
                status=status,
                available=True,
                region_id=region.id,
                provider=ProviderName.NASA_FIRMS.value,
                product=self.settings.firms_product,
                retrieved_at=retrieved_at,
                latest_detection_at=latest_detection_at,
                count_24h=count_24h,
                count_48h=count_48h,
                count_7d=count_7d,
                nearest_hotspot_distance_km=nearest,
                records=records,
                message="NASA FIRMS active-fire detections from database-backed ingestion.",
            )
        except (SQLAlchemyError, OSError) as exc:
            return self._unavailable(region.id, f"Hotspot database aggregation is unavailable: {exc.__class__.__name__}.")

    def summaries(self) -> list[HotspotSummary]:
        return [self.summary_for_region(region.id) for region in list_region_locations()]

    def to_canonical_data(self, summary: HotspotSummary) -> CanonicalHotspotData | MissingEnvironmentalData:
        if not summary.available:
            return MissingEnvironmentalData(status=summary.status, reason=summary.message or "Hotspot data unavailable.")
        values = {
            "hotspot_count_24h": summary.count_24h or 0,
            "hotspot_count_48h": summary.count_48h or 0,
            "hotspot_count_7d": summary.count_7d or 0,
            "hotspot_density": None,
            "nearest_hotspot_distance_km": summary.nearest_hotspot_distance_km,
        }
        return CanonicalHotspotData(
            status=summary.status,
            provider=summary.provider,
            source_type=summary.source_type,
            hotspot_count_24h=summary.count_24h or 0,
            hotspot_count_48h=summary.count_48h or 0,
            hotspot_count_7d=summary.count_7d or 0,
            hotspot_density=None,
            nearest_hotspot_distance_km=summary.nearest_hotspot_distance_km,
            latest_detection_at=summary.latest_detection_at.isoformat() if summary.latest_detection_at else None,
            retrieved_at=summary.retrieved_at.isoformat() if summary.retrieved_at else None,
            records=summary.records,
            values=values,
        )

    def _status_from_timestamps(self, retrieved_at: datetime | None, latest_detection_at: datetime | None, last_ingestion: dict[str, Any] | None) -> DataQualityStatus:
        if last_ingestion and last_ingestion.get("status") in {DataQualityStatus.UNAVAILABLE.value, DataQualityStatus.SUSPICIOUS.value}:
            return DataQualityStatus(last_ingestion["status"])
        if not retrieved_at:
            return DataQualityStatus.UNAVAILABLE
        now = datetime.now(timezone.utc)
        age_source = latest_detection_at or retrieved_at
        if age_source.tzinfo is None:
            age_source = age_source.replace(tzinfo=timezone.utc)
        policy = FreshnessPolicy.from_settings(self.settings)
        age = now - age_source
        if age > policy.hotspot_max_age:
            return DataQualityStatus.STALE
        if age > timedelta(hours=max(1, self.settings.firms_lookback_hours // 2)):
            return DataQualityStatus.RECENT
        return DataQualityStatus.LIVE

    def _last_ingestion(self, region_id: str) -> dict[str, Any] | None:
        setting = self.db.query(SystemSetting).filter(SystemSetting.key == f"firms:last_ingestion:{region_id}").first()
        return setting.value if setting else None

    def _record_to_schema(self, record) -> HotspotDetection:
        return HotspotDetection(
            id=record.id,
            latitude=record.latitude,
            longitude=record.longitude,
            detected_at=self._iso(record.detected_at),
            retrieved_at=self._iso(record.retrieved_at),
            satellite=record.satellite,
            instrument=record.instrument,
            confidence=record.confidence,
            severity=record.severity,
            frp=record.frp,
            brightness=record.brightness,
            source_record_id=record.source_record_id,
        )

    def _nearest_distance(self, latitude: float, longitude: float, records: list[HotspotDetection]) -> float | None:
        if not records:
            return None
        return round(min(self._haversine_km(latitude, longitude, record.latitude, record.longitude) for record in records), 3)

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_km = 6371.0088
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _unavailable(self, region_id: str, message: str) -> HotspotSummary:
        return HotspotSummary(
            status=DataQualityStatus.UNAVAILABLE,
            available=False,
            region_id=region_id,
            provider=ProviderName.NASA_FIRMS.value,
            product=self.settings.firms_product,
            retrieved_at=None,
            latest_detection_at=None,
            count_24h=None,
            count_48h=None,
            count_7d=None,
            nearest_hotspot_distance_km=None,
            records=[],
            message=message,
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    def _iso(self, value: datetime | None) -> str | None:
        if not value:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
