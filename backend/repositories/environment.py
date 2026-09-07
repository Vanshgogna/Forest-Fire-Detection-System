from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from backend.database.models import AIPrediction, Alert, FireHotspot, Region, SatelliteImage, VegetationRecord, WeatherRecord
from backend.repositories.base import BaseRepository
from backend.repositories.base import clamp_query_window


class RegionRepository(BaseRepository[Region]):
    def __init__(self, db: Session):
        super().__init__(Region, db)

    def search(self, query: str | None = None, state: str | None = None, skip: int = 0, limit: int = 100) -> list[Region]:
        skip, limit = clamp_query_window(skip, limit)
        statement = self.db.query(Region)
        if query:
            statement = statement.filter(Region.name.ilike(f"%{query}%"))
        if state:
            statement = statement.filter(Region.state == state)
        return list(statement.order_by(Region.name).offset(skip).limit(limit).all())

    def get_or_create_from_registry(self, registry_region) -> Region:
        region = self.db.get(Region, registry_region.database_id)
        if region:
            return region
        region = self.db.query(Region).filter(Region.name == registry_region.name).first()
        if region:
            return region
        region = Region(
            id=registry_region.database_id,
            name=registry_region.name,
            state=registry_region.state,
            latitude=registry_region.latitude,
            longitude=registry_region.longitude,
            centroid_geojson={"type": "Point", "coordinates": [registry_region.longitude, registry_region.latitude]},
        )
        self.db.add(region)
        self.db.flush()
        return region


class WeatherRepository(BaseRepository[WeatherRecord]):
    def __init__(self, db: Session):
        super().__init__(WeatherRecord, db)

    def latest_for_region(self, region_id: int) -> WeatherRecord | None:
        return (
            self.db.query(WeatherRecord)
            .filter(WeatherRecord.region_id == region_id)
            .order_by(desc(WeatherRecord.observed_at))
            .first()
        )


class VegetationRepository(BaseRepository[VegetationRecord]):
    def __init__(self, db: Session):
        super().__init__(VegetationRecord, db)

    def latest_for_region(self, region_id: int) -> VegetationRecord | None:
        return (
            self.db.query(VegetationRecord)
            .filter(VegetationRecord.region_id == region_id)
            .order_by(desc(VegetationRecord.captured_at))
            .first()
        )


class SatelliteImageRepository(BaseRepository[SatelliteImage]):
    def __init__(self, db: Session):
        super().__init__(SatelliteImage, db)

    def by_product_id(self, provider: str, product_id: str) -> SatelliteImage | None:
        return (
            self.db.query(SatelliteImage)
            .filter(SatelliteImage.provider == provider, SatelliteImage.product_id == product_id)
            .first()
        )

    def latest_sentinel_for_region(self, region_id: int) -> SatelliteImage | None:
        return (
            self.db.query(SatelliteImage)
            .filter(SatelliteImage.region_id == region_id, SatelliteImage.provider == "sentinel-2")
            .order_by(desc(SatelliteImage.captured_at), desc(SatelliteImage.retrieved_at))
            .first()
        )

    def latest_for_region(self, region_id: int) -> SatelliteImage | None:
        return (
            self.db.query(SatelliteImage)
            .filter(SatelliteImage.region_id == region_id)
            .order_by(desc(SatelliteImage.captured_at), desc(SatelliteImage.retrieved_at))
            .first()
        )


class PredictionRepository(BaseRepository[AIPrediction]):
    def __init__(self, db: Session):
        super().__init__(AIPrediction, db)

    def latest(self, region_id: int | None = None, limit: int = 25) -> list[AIPrediction]:
        _, limit = clamp_query_window(0, limit)
        statement = self.db.query(AIPrediction)
        if region_id:
            statement = statement.filter(AIPrediction.region_id == region_id)
        return list(statement.order_by(desc(AIPrediction.generated_at)).limit(limit).all())


class AlertRepository(BaseRepository[Alert]):
    def __init__(self, db: Session):
        super().__init__(Alert, db)

    def open_alerts(self, severity: str | None = None, limit: int = 100) -> list[Alert]:
        _, limit = clamp_query_window(0, limit)
        statement = self.db.query(Alert).filter(Alert.status.in_(["new", "acknowledged"]))
        if severity:
            statement = statement.filter(Alert.severity == severity)
        return list(statement.order_by(desc(Alert.created_at)).limit(limit).all())


class HotspotRepository(BaseRepository[FireHotspot]):
    def __init__(self, db: Session):
        super().__init__(FireHotspot, db)

    def between(self, start: datetime, end: datetime, region_id: int | None = None) -> list[FireHotspot]:
        _, limit = clamp_query_window(0, None)
        statement = self.db.query(FireHotspot).filter(FireHotspot.detected_at.between(start, end))
        if region_id:
            statement = statement.filter(FireHotspot.region_id == region_id)
        return list(statement.order_by(desc(FireHotspot.detected_at)).limit(limit).all())

    def count_since(self, region_id: int, since: datetime) -> int:
        return int(self.db.query(func.count(FireHotspot.id)).filter(FireHotspot.region_id == region_id, FireHotspot.detected_at >= since).scalar() or 0)

    def latest_for_region(self, region_id: int) -> FireHotspot | None:
        return (
            self.db.query(FireHotspot)
            .filter(FireHotspot.region_id == region_id)
            .order_by(desc(FireHotspot.detected_at))
            .first()
        )

    def latest_retrieved_for_region(self, region_id: int) -> FireHotspot | None:
        return (
            self.db.query(FireHotspot)
            .filter(FireHotspot.region_id == region_id, FireHotspot.retrieved_at.isnot(None))
            .order_by(desc(FireHotspot.retrieved_at))
            .first()
        )

    def by_source_record_id(self, provider: str, source_record_id: str) -> FireHotspot | None:
        return (
            self.db.query(FireHotspot)
            .filter(FireHotspot.provider == provider, FireHotspot.source_record_id == source_record_id)
            .first()
        )

    def recent_for_region(self, region_id: int, since: datetime, limit: int = 100) -> list[FireHotspot]:
        _, limit = clamp_query_window(0, limit)
        return list(
            self.db.query(FireHotspot)
            .filter(FireHotspot.region_id == region_id, FireHotspot.detected_at >= since)
            .order_by(desc(FireHotspot.detected_at))
            .limit(limit)
            .all()
        )

    def add_or_update_from_firms(self, record) -> tuple[FireHotspot, bool]:
        existing = self.by_source_record_id(record.provider, record.source_record_id)
        if existing:
            existing.retrieved_at = record.retrieved_at
            existing.quality_status = record.quality_status.value
            existing.provenance_metadata = record.provenance_metadata
            return existing, False

        hotspot = FireHotspot(
            region_id=record.database_region_id,
            detected_at=record.detected_at,
            latitude=record.latitude,
            longitude=record.longitude,
            confidence=record.confidence,
            severity=record.severity,
            source=record.product,
            provider=record.provider,
            source_record_id=record.source_record_id,
            retrieved_at=record.retrieved_at,
            satellite=record.satellite,
            instrument=record.instrument,
            brightness=record.brightness,
            frp=record.frp,
            scan=record.scan,
            track=record.track,
            daynight=record.daynight,
            quality_status=record.quality_status.value,
            provenance_metadata=record.provenance_metadata,
        )
        self.db.add(hotspot)
        self.db.flush()
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            self.db.execute(
                text("UPDATE fire_hotspots SET geometry = ST_SetSRID(ST_Point(:lon, :lat), 4326) WHERE id = :id"),
                {"lon": record.longitude, "lat": record.latitude, "id": hotspot.id},
            )
        else:
            hotspot.geometry = f"POINT({record.longitude} {record.latitude})"
        return hotspot, True
