from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.core.config import Settings, get_settings
from backend.ml.features import FEATURE_COLUMNS, FEATURE_DEFAULTS, build_fire_risk_features
from backend.ml.pipeline import FireRiskModelService, PredictionResult
from backend.schemas.environmental import CanonicalHotspotData, CanonicalVegetationData, CanonicalWeatherData, EnvironmentalSnapshot, MissingEnvironmentalData
from backend.services.environmental_data_service import EnvironmentalDataService
from backend.services.environmental_foundation import DataMode
from backend.services.region_registry import get_region_location

logger = logging.getLogger("firesight.prediction")


@dataclass(frozen=True)
class LivePredictionUnavailable:
    region_id: str
    region: str
    data_mode: str
    missing_sources: list[dict[str, str]]
    snapshot: EnvironmentalSnapshot | None = None
    message: str = "Live environmental data is unavailable for prediction."

    def to_response(self) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "region_id": self.region_id,
            "region": self.region,
            "data_mode": self.data_mode,
            "message": self.message,
            "missing_sources": self.missing_sources,
            "availability": self.snapshot.availability if self.snapshot else {},
            "data_quality": self.snapshot.quality if self.snapshot else {},
            "data_provenance": self.snapshot.provenance if self.snapshot else {},
        }


class LivePredictionService:
    """Compose canonical environmental snapshots into the existing ML service."""

    def __init__(
        self,
        environmental_service: EnvironmentalDataService | None = None,
        model_service: FireRiskModelService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.environmental_service = environmental_service or EnvironmentalDataService(settings=self.settings)
        self.model_service = model_service or FireRiskModelService()

    def predict_region(self, region_id: str) -> dict[str, Any]:
        if self.settings.data_mode == DataMode.SIMULATION.value:
            return self._simulation_prediction(region_id)

        region = get_region_location(region_id)
        snapshot = self.environmental_service.get_environmental_snapshot(region_id)
        features, missing_sources, defaulted_features = self.features_from_snapshot(snapshot)
        logger.info(
            "prediction_inputs_evaluated region_id=%s required_inputs=%s available_inputs=%s missing_sources=%s defaulted_features=%s",
            region_id,
            list(FEATURE_COLUMNS),
            sorted(features.keys()),
            missing_sources,
            defaulted_features,
        )
        if missing_sources:
            logger.warning("prediction_unavailable region_id=%s missing_sources=%s", region_id, missing_sources)
            return LivePredictionUnavailable(
                region_id=region_id,
                region=region.name,
                data_mode=self.settings.data_mode,
                missing_sources=missing_sources,
                snapshot=snapshot,
            ).to_response()

        try:
            result = self.model_service.predict(features)
        except Exception as exc:
            return {
                "status": "unavailable",
                "region_id": region_id,
                "region": region.name,
                "data_mode": self.settings.data_mode,
                "message": f"Prediction model is unavailable: {exc.__class__.__name__}.",
                "missing_sources": [{"source": "model", "status": "UNAVAILABLE", "reason": exc.__class__.__name__}],
                "availability": snapshot.availability,
                "data_quality": snapshot.quality,
                "data_provenance": snapshot.provenance,
            }

        return self._prediction_response(region_id, region.name, snapshot, features, result, defaulted_features)

    def features_from_snapshot(self, snapshot: EnvironmentalSnapshot) -> tuple[dict[str, float], list[dict[str, str]], list[str]]:
        values: dict[str, float] = {}
        missing: list[dict[str, str]] = []
        defaulted: list[str] = []
        missing_features_by_source: set[str] = set()

        weather = snapshot.weather
        if isinstance(weather, CanonicalWeatherData):
            values.update(
                {
                    "temperature": weather.temperature,
                    "humidity": weather.humidity,
                    "wind_speed": weather.wind_speed,
                    "rainfall": weather.precipitation,
                    "fire_weather_index": weather.fire_weather_index,
                }
            )
        else:
            missing.append(self._missing_source("weather", weather))
            missing_features_by_source.update({"temperature", "humidity", "wind_speed", "rainfall", "fire_weather_index"})

        vegetation = snapshot.vegetation
        if isinstance(vegetation, CanonicalVegetationData):
            values["ndvi"] = vegetation.ndvi_mean
            if isinstance(vegetation.values.get("nbr"), (int, float)):
                values["nbr"] = float(vegetation.values["nbr"])
        else:
            missing.append(self._missing_source("vegetation", vegetation))
            missing_features_by_source.add("ndvi")

        hotspots = snapshot.hotspots
        if isinstance(hotspots, CanonicalHotspotData):
            values["hotspots"] = float(hotspots.hotspot_count_24h)
        else:
            missing.append(self._missing_source("hotspots", hotspots))
            missing_features_by_source.add("hotspots")

        if "nbr" in FEATURE_COLUMNS and "nbr" not in values:
            values["nbr"] = FEATURE_DEFAULTS["nbr"]
            defaulted.append("nbr")

        feature_missing = [feature for feature in FEATURE_COLUMNS if feature not in values and feature not in missing_features_by_source]
        missing.extend({"source": "feature", "status": "UNAVAILABLE", "reason": f"Missing required ML feature: {feature}"} for feature in feature_missing)
        if missing:
            return values, missing, defaulted
        return build_fire_risk_features(values), missing, defaulted

    def _prediction_response(
        self,
        region_id: str,
        region_name: str,
        snapshot: EnvironmentalSnapshot,
        features: dict[str, float],
        result: PredictionResult,
        defaulted_features: list[str],
    ) -> dict[str, Any]:
        explanation = result.explanation_details
        return {
            "status": "ok",
            "region_id": region_id,
            "region": region_name,
            "risk_score": result.risk_score,
            "risk_level": result.risk_category,
            "confidence": result.confidence,
            "model_version": self.model_service.model_version,
            "feature_schema": list(FEATURE_COLUMNS),
            "feature_values": features,
            "defaulted_features": defaulted_features,
            "input_snapshot": {
                "region": region_name,
                "region_id": region_id,
                **features,
                "source": "environmental_snapshot",
                "snapshot_timestamp": snapshot.timestamp.isoformat(),
            },
            "explanation": result.explanation,
            "explanation_details": explanation,
            "top_contributing_features": explanation["top_contributing_features"],
            "feature_importance": explanation["feature_importance"],
            "risk_factors": explanation["risk_factors"],
            "historical_comparison": explanation["historical_comparison"],
            "weather_influence": explanation["weather_influence"],
            "vegetation_influence": explanation["vegetation_influence"],
            "historical_trend_influence": explanation["historical_trend_influence"],
            "confidence_explanation": explanation["confidence_explanation"],
            "visual_explanations": explanation["visual_explanations"],
            "interpretability": explanation["interpretability"],
            "recommendation_rationales": explanation["recommendation_rationales"],
            "recommendations": result.recommendations,
            "data_mode": snapshot.data_mode,
            "availability": snapshot.availability,
            "data_quality": snapshot.quality,
            "data_provenance": snapshot.provenance,
        }

    def _simulation_prediction(self, region_id: str) -> dict[str, Any]:
        from backend.services.mock_environment import REGIONS

        region = next((item for item in REGIONS if item.id == region_id), None)
        if region is None:
            get_region_location(region_id)
        features = build_fire_risk_features(
            {
                "temperature": region.temperature,
                "humidity": region.humidity,
                "wind_speed": region.wind_speed,
                "rainfall": region.rainfall,
                "ndvi": region.ndvi,
                "nbr": region.nbr,
                "hotspots": region.hotspots,
            }
        )
        result = self.model_service.predict(features)
        return self._prediction_response(
            region_id=region_id,
            region_name=region.name,
            snapshot=self._simulation_snapshot(region),
            features=features,
            result=result,
            defaulted_features=["fire_weather_index"],
        )

    def _simulation_snapshot(self, region) -> EnvironmentalSnapshot:
        from datetime import datetime, timezone

        return EnvironmentalSnapshot(
            region_id=region.id,
            timestamp=datetime.now(timezone.utc),
            data_mode=DataMode.SIMULATION.value,
            region={
                "region_id": region.id,
                "region": region.name,
                "state": region.state,
                "latitude": region.coordinates[0],
                "longitude": region.coordinates[1],
            },
            weather=MissingEnvironmentalData(status="SIMULATED", reason="Simulation mode uses development fixture weather for prediction."),
            vegetation=MissingEnvironmentalData(status="SIMULATED", reason="Simulation mode uses development fixture NDVI for prediction."),
            hotspots=MissingEnvironmentalData(status="SIMULATED", reason="Simulation mode uses development fixture hotspots for prediction."),
            provenance={},
            quality={"overall_status": "SIMULATED", "weather_status": "SIMULATED", "vegetation_status": "SIMULATED", "hotspot_status": "SIMULATED"},
            availability={"weather_available": True, "vegetation_available": True, "hotspots_available": True},
        )

    def _missing_source(self, source: str, payload: MissingEnvironmentalData) -> dict[str, str]:
        return {"source": source, "status": str(payload.status), "reason": payload.reason}
