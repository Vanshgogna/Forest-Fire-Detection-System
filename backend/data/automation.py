from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.data.pipeline import PipelineManifest
from backend.data.sources import RefreshMode


@dataclass(frozen=True)
class PipelineRefreshPlan:
    """Serializable automation plan for scheduled and incremental ETL refreshes."""

    dataset_id: str
    dataset_version: str
    source: str
    refresh_mode: RefreshMode
    schedule_cron: str | None
    incremental_field: str | None
    last_watermark: str | None
    checkpoint_enabled: bool
    task_name: str
    reason: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["refresh_mode"] = self.refresh_mode.value
        return payload


class PipelineAutomationPlanner:
    """Create scheduled refresh, incremental processing, and recovery plans for workers."""

    task_name = "firesight.run_data_pipeline"

    def plan(self, manifest: PipelineManifest) -> PipelineRefreshPlan:
        policy = manifest.source.refresh_policy
        if policy.mode == RefreshMode.SCHEDULED and policy.schedule_cron:
            reason = f"scheduled refresh on cron {policy.schedule_cron}"
        elif policy.mode == RefreshMode.INCREMENTAL and policy.incremental_field:
            reason = f"incremental refresh using watermark field {policy.incremental_field}"
        else:
            reason = "manual refresh"
        return PipelineRefreshPlan(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.dataset_version,
            source=manifest.source.name,
            refresh_mode=policy.mode,
            schedule_cron=policy.schedule_cron,
            incremental_field=policy.incremental_field,
            last_watermark=policy.last_watermark,
            checkpoint_enabled=policy.checkpoint_enabled,
            task_name=self.task_name,
            reason=reason,
        )

    def should_process_increment(self, manifest: PipelineManifest, candidate_watermark: str | None) -> bool:
        policy = manifest.source.refresh_policy
        if policy.mode != RefreshMode.INCREMENTAL:
            return True
        if not candidate_watermark:
            return False
        if not policy.last_watermark:
            return True
        return candidate_watermark > policy.last_watermark
