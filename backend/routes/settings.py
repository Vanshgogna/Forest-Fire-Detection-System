from fastapi import APIRouter, Depends

from backend.core.config import get_settings as load_settings
from backend.core.security import Principal, require_admin

router = APIRouter()


@router.get("/")
def get_settings():
    settings = load_settings()
    return {
        "auto_refresh_seconds": 300,
        "critical_risk_threshold": settings.critical_risk_threshold,
        "high_risk_threshold": settings.high_risk_threshold,
        "notifications": ["dashboard", "email", "future_sms"],
        "api_version": settings.api_version,
    }


@router.put("/")
def update_settings(payload: dict, _: Principal = Depends(require_admin)):
    return {"status": "accepted", "updated": payload}
