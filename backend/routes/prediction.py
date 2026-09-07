from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from backend.core.security import Principal, require_researcher
from backend.ml.pipeline import FireRiskModelService
from backend.models.environment import PredictionRequest, PredictionResponse
from backend.schemas.domain import ModelTrainingRequest, PredictionJobRequest
from backend.services.live_prediction_service import LivePredictionService
from backend.services.mock_environment import REGIONS
from backend.services.weather_provider import OpenMeteoWeatherProvider

router = APIRouter()
model_service = FireRiskModelService()
weather_provider = OpenMeteoWeatherProvider()
live_prediction_service = LivePredictionService(model_service=model_service)


@router.get("/")
def get_predictions():
    return {
        "source_type": "simulated_development_fixture",
        "message": "Prediction list uses development fixture regions. Use POST /api/prediction with canonical weather data for live scoring.",
        "predictions": [
            {"region": region.name, "risk_score": region.risk_score, "risk_level": region.risk_level, "confidence": region.confidence}
            for region in REGIONS
        ]
    }


@router.post("/", response_model=PredictionResponse)
def predict_fire_risk(payload: PredictionRequest):
    result = model_service.predict(payload.model_dump())
    explanation = result.explanation_details
    return PredictionResponse(
        region=payload.region,
        risk_score=result.risk_score,
        risk_level=result.risk_category,
        confidence=result.confidence,
        input_snapshot={
            "region": payload.region,
            "temperature": payload.temperature,
            "humidity": payload.humidity,
            "wind_speed": payload.wind_speed,
            "rainfall": payload.rainfall,
            "fire_weather_index": payload.fire_weather_index,
            "ndvi": payload.ndvi,
            "nbr": payload.nbr,
            "hotspots": payload.hotspots,
            "source": "request_payload",
        },
        explanation=result.explanation,
        explanation_details=explanation,
        top_contributing_features=explanation["top_contributing_features"],
        feature_importance=explanation["feature_importance"],
        risk_factors=explanation["risk_factors"],
        historical_comparison=explanation["historical_comparison"],
        weather_influence=explanation["weather_influence"],
        vegetation_influence=explanation["vegetation_influence"],
        historical_trend_influence=explanation["historical_trend_influence"],
        confidence_explanation=explanation["confidence_explanation"],
        visual_explanations=explanation["visual_explanations"],
        interpretability=explanation["interpretability"],
        recommendation_rationales=explanation["recommendation_rationales"],
        recommendations=result.recommendations,
    )


@router.post("/batch")
def batch_predict(payloads: list[dict]):
    return {"predictions": [jsonable_encoder(prediction) for prediction in model_service.batch_predict(payloads)]}


@router.post("/jobs")
def schedule_prediction_job(payload: PredictionJobRequest, _: Principal = Depends(require_researcher)):
    selected_regions = payload.region_ids or [int(region.id.replace("R", "")) for region in REGIONS if region.id.replace("R", "").isdigit()]
    return {
        "status": "queued" if payload.run_async else "completed",
        "region_ids": selected_regions,
        "include_explainability": payload.include_explainability,
        "job_type": "scheduled_prediction",
    }


@router.post("/train")
def train_model(payload: ModelTrainingRequest, _: Principal = Depends(require_researcher)):
    return model_service.training_plan(
        algorithm=payload.algorithm,
        target_column=payload.target_column,
        tune_hyperparameters=payload.tune_hyperparameters,
        persist_model=payload.persist_model,
    )


@router.get("/explainability")
def explainability():
    weather = weather_provider.weather_for_region(region_id="r1")
    current = weather.get("current") or {}
    if weather.get("status") != "ok":
        return {
            "status": "unavailable",
            "source": weather.get("source"),
            "message": "Live weather is required before generating a current explainability sample.",
            "weather": weather,
        }
    sample = model_service.predict(
        {
            "temperature": current["temperature"],
            "humidity": current["humidity"],
            "wind_speed": current["wind_speed"],
            "rainfall": current["rainfall"],
            "fire_weather_index": current["fire_weather_risk_index"],
            "ndvi": 0.31,
            "nbr": 0.18,
            "hotspots": 18,
        }
    )
    sample.explanation_details["weather_source"] = {
        "provider": weather["provider"],
        "location": weather["location"],
        "observed_at": current["observed_at"],
        "retrieved_at": weather["retrieved_at"],
        "cache": weather["cache"],
    }
    return jsonable_encoder(sample)


@router.get("/{region_id}")
def predict_region_from_environment(region_id: str):
    try:
        return jsonable_encoder(live_prediction_service.predict_region(region_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
