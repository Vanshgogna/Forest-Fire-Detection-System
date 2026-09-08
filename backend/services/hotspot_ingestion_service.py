from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database.models import SystemSetting
from backend.repositories.environment import HotspotRepository, RegionRepository
from backend.services.environmental_foundation import DataQualityStatus, ProviderErrorKind
from backend.services.firms_provider import FIRMSProvider
from backend.services.region_registry import get_region_location, list_region_locations

logger = logging.getLogger("firesight.firms")


@dataclass(frozen=True)
class FIRMSIngestionResult:
    records_received: int
    records_valid: int
    records_invalid: int
    records_inserted: int
    records_updated: int
    records_skipped: int
    duplicates: int
    regions_processed: int
    provider: str
    product: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    status: DataQualityStatus
    error_type: ProviderErrorKind | None = None
    message: str | None = None
    latest_detection_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "records_received": self.records_received,
            "records_valid": self.records_valid,
            "records_invalid": self.records_invalid,
            "records_inserted": self.records_inserted,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "duplicates": self.duplicates,
            "regions_processed": self.regions_processed,
            "provider": self.provider,
            "product": self.product,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "status": self.status.value,
            "error_type": self.error_type.value if self.error_type else None,
            "message": self.message,
            "latest_detection_at": self.latest_detection_at.isoformat() if self.latest_detection_at else None,
        }


class FIRMSIngestionService:
    def __init__(self, db: Session, provider: FIRMSProvider | None = None):
        self.db = db
        self.provider = provider or FIRMSProvider()

    def ingest_regions(self, region_ids: list[str] | None = None) -> FIRMSIngestionResult:
        target_regions = [get_region_location(region_id) for region_id in region_ids] if region_ids else list_region_locations()
        started_at = datetime.now(timezone.utc)
        timer = perf_counter()
        totals = {
            "records_received": 0,
            "records_valid": 0,
            "records_invalid": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "duplicates": 0,
        }
        status = DataQualityStatus.LIVE
        error_type: ProviderErrorKind | None = None
        message: str | None = None
        latest_detection_at: datetime | None = None
        region_repo = RegionRepository(self.db)
        hotspot_repo = HotspotRepository(self.db)

        for region in target_regions:
            provider_result = self.provider.fetch_active_fires(region.id)
            totals["records_received"] += provider_result.records_received
            totals["records_valid"] += provider_result.records_valid
            totals["records_invalid"] += provider_result.records_invalid
            if provider_result.error:
                status = provider_result.status
                error_type = provider_result.error.kind
                message = provider_result.error.message
                self._persist_region_status(region.id, provider_result, None, 0, 0, 0)
                self.db.commit()
                continue

            try:
                region_row = region_repo.get_or_create_from_registry(region)
                inserted = 0
                updated = 0
                duplicates = 0
                for record in provider_result.records:
                    persisted, created = hotspot_repo.add_or_update_from_firms(record)
                    if created:
                        inserted += 1
                    else:
                        updated += 1
                        duplicates += 1
                    if latest_detection_at is None or persisted.detected_at > latest_detection_at:
                        latest_detection_at = persisted.detected_at

                totals["records_inserted"] += inserted
                totals["records_updated"] += updated
                totals["duplicates"] += duplicates
                totals["records_skipped"] += provider_result.records_received - provider_result.records_valid
                self._persist_region_status(region.id, provider_result, region_row.id, inserted, updated, duplicates)
                self.db.commit()
            except SQLAlchemyError as exc:
                self.db.rollback()
                status = DataQualityStatus.UNAVAILABLE
                error_type = ProviderErrorKind.DATABASE_ERROR
                message = str(exc)
                logger.exception("firms_ingestion_database_error")
                break
        completed_at = datetime.now(timezone.utc)
        result = FIRMSIngestionResult(
            **totals,
            regions_processed=len(target_regions),
            provider=self.provider.provider,
            product=self.provider.settings.firms_product,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(perf_counter() - timer, 3),
            status=status,
            error_type=error_type,
            message=message,
            latest_detection_at=latest_detection_at,
        )
        logger.info(
            "firms_ingestion_completed provider=%s product=%s regions_processed=%s records_received=%s records_valid=%s records_inserted=%s duplicates=%s status=%s error_type=%s",
            result.provider,
            result.product,
            result.regions_processed,
            result.records_received,
            result.records_valid,
            result.records_inserted,
            result.duplicates,
            result.status.value,
            result.error_type.value if result.error_type else None,
        )
        return result

    def _persist_region_status(self, region_id: str, provider_result, database_region_id: int | None, inserted: int, updated: int, duplicates: int) -> None:
        key = f"firms:last_ingestion:{region_id}"
        latest_detection_at = max((record.detected_at for record in provider_result.records), default=None)
        payload = {
            "region_id": region_id,
            "database_region_id": database_region_id,
            "provider": provider_result.provider,
            "product": provider_result.product,
            "status": provider_result.status.value,
            "retrieved_at": provider_result.retrieved_at.isoformat(),
            "latest_detection_at": latest_detection_at.isoformat() if latest_detection_at else None,
            "records_received": provider_result.records_received,
            "records_valid": provider_result.records_valid,
            "records_invalid": provider_result.records_invalid,
            "records_inserted": inserted,
            "records_updated": updated,
            "duplicates": duplicates,
            "error_type": provider_result.error.kind.value if provider_result.error else None,
            "message": provider_result.error.message if provider_result.error else None,
        }
        setting = self.db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = payload
        else:
            self.db.add(SystemSetting(key=key, value=payload, description="Last NASA FIRMS ingestion result for a monitored region."))
