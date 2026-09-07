from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from backend.core.security import Principal, require_operator
from backend.schemas.domain import AlertUpdate
from backend.services.alert_engine import AlertEngine
from backend.services.live_prediction_service import LivePredictionService
from backend.services.mock_environment import ALERTS

router = APIRouter()
engine = AlertEngine()
live_prediction_service = LivePredictionService()


def _fixture_alert(alert) -> dict[str, Any]:
    return {**alert.__dict__, "source": "simulation", "data_mode": "simulation"}


def _live_alert(alert: dict[str, Any], prediction: dict[str, Any], index: int) -> dict[str, Any]:
    recommendations = prediction.get("recommendations") or ["Review the current prediction explanation before taking operational action."]
    generated_at = prediction.get("input_snapshot", {}).get("snapshot_timestamp") or datetime.now(timezone.utc).isoformat()
    return {
        "id": f"LIVE-{prediction.get('region_id', 'region').upper()}-{index + 1}",
        "title": alert["title"],
        "region": prediction["region"],
        "severity": alert["severity"],
        "confidence": prediction["confidence"],
        "status": "New",
        "generated_at": generated_at,
        "explanation": alert["reason"],
        "actions": recommendations[:3],
        "source": "live_prediction",
        "data_mode": prediction.get("data_mode", "live"),
        "risk_score": prediction["risk_score"],
        "risk_level": prediction["risk_level"],
    }


def _alert_inputs_from_prediction(prediction: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    features = prediction.get("feature_values") or {}
    weather = {
        "temperature": features.get("temperature"),
        "humidity": features.get("humidity"),
        "wind_speed": features.get("wind_speed"),
        "rainfall": features.get("rainfall"),
        "fire_weather_index": features.get("fire_weather_index"),
    }
    vegetation = {
        "ndvi": features.get("ndvi"),
        "nbr": features.get("nbr"),
    }
    return prediction, weather, vegetation


@router.get("/")
def get_alerts():
    return {"status": "simulation", "alerts": [_fixture_alert(alert) for alert in ALERTS]}


@router.post("/evaluate")
def evaluate_alerts(payload: dict):
    return {
        "alerts": engine.evaluate(
            prediction=payload.get("prediction", {}),
            weather=payload.get("weather", {}),
            vegetation=payload.get("vegetation", {}),
        )
    }


@router.get("/evaluate/{region_id}")
def evaluate_region_alerts(region_id: str):
    prediction = live_prediction_service.predict_region(region_id)
    if prediction.get("status") != "ok":
        return {
            "status": "unavailable",
            "region_id": region_id,
            "region": prediction.get("region"),
            "prediction_status": prediction.get("status", "unavailable"),
            "message": prediction.get("message", "Live prediction unavailable; no alert was generated."),
            "alerts": [],
            "missing_sources": prediction.get("missing_sources", []),
            "source": "live_prediction",
        }

    alert_input, weather_input, vegetation_input = _alert_inputs_from_prediction(prediction)
    evaluated_alerts = engine.evaluate(prediction=alert_input, weather=weather_input, vegetation=vegetation_input)
    return {
        "status": "ok",
        "region_id": region_id,
        "region": prediction["region"],
        "prediction_status": prediction["status"],
        "message": "Live prediction evaluated below alert thresholds." if not evaluated_alerts else "Live prediction evaluated by existing alert engine.",
        "alerts": [_live_alert(alert, prediction, index) for index, alert in enumerate(evaluated_alerts)],
        "source": "live_prediction",
    }


@router.patch("/{alert_id}")
def update_alert(alert_id: str, payload: AlertUpdate, principal: Principal = Depends(require_operator)):
    return {
        "id": alert_id,
        "status": payload.status,
        "acknowledged_by": payload.acknowledged_by or principal.subject,
        "resolution_notes": payload.resolution_notes,
    }
