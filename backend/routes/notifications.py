from fastapi import APIRouter, Depends

from backend.core.security import Principal, require_operator
from backend.services.notification_service import NotificationService

router = APIRouter()
service = NotificationService()


@router.post("/")
def queue_notification(payload: dict, _: Principal = Depends(require_operator)):
    return service.build_notification(
        channel=payload.get("channel", "dashboard"),
        recipient=payload.get("recipient", "control-room"),
        subject=payload.get("subject", "Forest fire intelligence alert"),
        body=payload.get("body", ""),
        metadata=payload.get("metadata", {}),
    )


@router.post("/alert-plan")
def alert_notification_plan(alert: dict):
    return service.alert_notification_plan(alert)
