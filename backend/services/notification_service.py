from __future__ import annotations

from datetime import datetime


class NotificationService:
    supported_channels = {"dashboard", "email", "sms", "webhook"}

    def build_notification(self, channel: str, recipient: str, subject: str, body: str, metadata: dict | None = None) -> dict:
        if channel not in self.supported_channels:
            return {"status": "rejected", "reason": f"Unsupported channel: {channel}", "supported": sorted(self.supported_channels)}
        return {
            "status": "queued",
            "channel": channel,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "metadata": metadata or {},
            "queued_at": datetime.utcnow().isoformat(),
            "provider": "future_provider_adapter",
        }

    def alert_notification_plan(self, alert: dict) -> dict:
        severity = alert.get("severity", "Moderate")
        channels = ["dashboard"]
        if severity in {"High", "Critical"}:
            channels.append("email")
        if severity == "Critical":
            channels.append("sms")
        return {"alert_id": alert.get("id"), "severity": severity, "channels": channels, "status": "ready"}
