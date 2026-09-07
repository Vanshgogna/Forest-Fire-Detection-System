from __future__ import annotations

from dataclasses import asdict, dataclass


WEATHER_FEATURES = {"temperature", "humidity", "wind_speed", "rainfall", "fire_weather_index"}
VEGETATION_FEATURES = {"ndvi", "nbr"}
HISTORICAL_FEATURES = {"hotspots"}


@dataclass(frozen=True)
class FeatureContribution:
    feature: str
    display_name: str
    value: float
    importance: float
    contribution: float
    direction: str
    influence_group: str
    explanation: str


@dataclass(frozen=True)
class PredictionExplanation:
    prediction: str
    confidence_score: int
    summary: str
    why: str
    top_contributing_features: list[dict]
    feature_importance: dict[str, float]
    risk_factors: list[str]
    weather_influence: list[str]
    vegetation_influence: list[str]
    historical_trend_influence: list[str]
    historical_comparison: dict
    confidence_explanation: str
    recommendation_rationales: list[dict]
    visual_explanations: dict
    interpretability: dict

    def to_dict(self) -> dict:
        return asdict(self)


class FireRiskExplanationEngine:
    """Build human-readable and chart-ready explanations for every prediction."""

    historical_average_risk = 49

    def explain(
        self,
        *,
        features: dict[str, float],
        risk_score: int,
        risk_category: str,
        confidence: int,
        feature_importance: dict[str, float],
        recommendations: list[str],
    ) -> PredictionExplanation:
        contributions = self._feature_contributions(features, feature_importance)
        top_contributors = sorted(contributions, key=lambda item: abs(item.contribution), reverse=True)[:5]
        risk_factors = [item.explanation for item in top_contributors if item.direction == "increases_risk"]
        if not risk_factors:
            risk_factors = ["No dominant high-risk driver is active; current risk is controlled by balanced weather and vegetation signals."]
        historical_comparison = self._historical_comparison(risk_score)
        why = self._why(risk_category, top_contributors, historical_comparison)
        recommendation_rationales = self._recommendation_rationales(recommendations, top_contributors, risk_score)
        visual_explanations = self._visual_explanations(risk_score, confidence, risk_category, contributions, historical_comparison)
        explanation = PredictionExplanation(
            prediction=risk_category,
            confidence_score=confidence,
            summary=f"Prediction: {risk_category} wildfire risk with {confidence}% confidence.",
            why=why,
            top_contributing_features=[asdict(item) for item in top_contributors],
            feature_importance=feature_importance,
            risk_factors=risk_factors,
            weather_influence=self._group_influence(top_contributors, "weather"),
            vegetation_influence=self._group_influence(top_contributors, "vegetation"),
            historical_trend_influence=self._group_influence(top_contributors, "historical"),
            historical_comparison=historical_comparison,
            confidence_explanation=self._confidence_explanation(confidence, features),
            recommendation_rationales=recommendation_rationales,
            visual_explanations=visual_explanations,
            interpretability={
                "current_method": "domain_heuristic_plus_model_feature_importance",
                "future_methods": ["SHAP", "LIME", "Permutation Importance", "Partial Dependence Plots"],
                "black_box_policy": "Every prediction must include drivers, confidence rationale, and human-readable recommendations.",
            },
        )
        self.validate(explanation)
        return explanation

    def validate(self, explanation: PredictionExplanation) -> None:
        required = [
            explanation.summary,
            explanation.why,
            explanation.top_contributing_features,
            explanation.feature_importance,
            explanation.confidence_explanation,
            explanation.visual_explanations,
            explanation.recommendation_rationales,
        ]
        if any(not item for item in required):
            raise ValueError("Prediction explanation is incomplete")

    def _feature_contributions(self, features: dict[str, float], feature_importance: dict[str, float]) -> list[FeatureContribution]:
        raw = {
            "temperature": min(30.0, features["temperature"] * 0.75),
            "humidity": min(30.0, (100.0 - features["humidity"]) * 0.32),
            "wind_speed": min(18.0, features["wind_speed"] * 0.65),
            "rainfall": -min(18.0, features["rainfall"] * 2.5),
            "ndvi": min(10.0, (1.0 - features["ndvi"]) * 12.0),
            "nbr": min(8.0, (1.0 - features["nbr"]) * 8.0),
            "hotspots": min(12.0, features["hotspots"] * 2.2),
            "fire_weather_index": min(8.0, features["fire_weather_index"] * 0.08),
        }
        return [
            FeatureContribution(
                feature=feature,
                display_name=self._display_name(feature),
                value=round(features[feature], 4),
                importance=feature_importance.get(feature, 0.0),
                contribution=round(contribution, 2),
                direction="reduces_risk" if contribution < 0 else "increases_risk",
                influence_group=self._influence_group(feature),
                explanation=self._feature_explanation(feature, features[feature], contribution),
            )
            for feature, contribution in raw.items()
        ]

    def _feature_explanation(self, feature: str, value: float, contribution: float) -> str:
        if feature == "temperature":
            return f"Temperature is {value:g}°C, adding heat stress to dry fuels."
        if feature == "humidity":
            return f"Humidity is {value:g}%, so fuels lose moisture protection quickly."
        if feature == "wind_speed":
            return f"Wind speed is {value:g} km/h, increasing potential fire spread."
        if feature == "rainfall":
            return f"Rainfall is {value:g} mm, reducing risk by {abs(round(contribution, 1)):g} points."
        if feature == "ndvi":
            return f"NDVI is {value:.2f}, indicating vegetation stress and dry fuel availability."
        if feature == "nbr":
            return f"NBR is {value:.2f}, showing burn-scar or vegetation stress pressure."
        if feature == "hotspots":
            return f"{value:g} recent hotspots raise concern because similar clusters preceded historical fire events."
        return f"Fire Weather Risk Index is {value:g}, showing combined weather pressure."

    def _why(self, risk_category: str, contributors: list[FeatureContribution], historical_comparison: dict) -> str:
        driver_names = ", ".join(item.display_name for item in contributors[:3])
        comparison = historical_comparison["comparison_text"]
        return f"The model predicted {risk_category} risk because {driver_names} are the strongest current drivers. {comparison}"

    def _group_influence(self, contributors: list[FeatureContribution], group: str) -> list[str]:
        messages = [item.explanation for item in contributors if item.influence_group == group]
        fallback = {
            "weather": "Weather variables are not the dominant driver in this prediction.",
            "vegetation": "Vegetation indices are stable enough that they are not the dominant driver.",
            "historical": "Historical hotspot trend is not the dominant driver for this prediction.",
        }
        return messages or [fallback[group]]

    def _historical_comparison(self, risk_score: int) -> dict:
        delta = risk_score - self.historical_average_risk
        direction = "above" if delta >= 0 else "below"
        return {
            "current_risk_score": risk_score,
            "historical_average_risk": self.historical_average_risk,
            "delta": delta,
            "direction": direction,
            "comparison_text": f"Current risk is {abs(delta)} points {direction} the historical seasonal average.",
            "chart": [
                {"label": "Historical Avg", "risk": self.historical_average_risk},
                {"label": "Current", "risk": risk_score},
            ],
        }

    def _confidence_explanation(self, confidence: int, features: dict[str, float]) -> str:
        completeness = sum(1 for value in features.values() if value is not None)
        if confidence >= 90:
            return f"Confidence is high because all {completeness} expected feature signals are available and the risk class is well separated."
        if confidence >= 75:
            return f"Confidence is moderate-high because all {completeness} expected feature signals are available, with some mixed risk drivers."
        return f"Confidence is cautious because the model sees weaker separation among risk classes despite {completeness} available feature signals."

    def _recommendation_rationales(self, recommendations: list[str], contributors: list[FeatureContribution], risk_score: int) -> list[dict]:
        primary_driver = contributors[0].display_name if contributors else "current risk drivers"
        return [
            {
                "recommendation": recommendation,
                "rationale": f"This action is recommended because {primary_driver} is pushing the risk score to {risk_score}/100.",
            }
            for recommendation in recommendations
        ]

    def _visual_explanations(
        self,
        risk_score: int,
        confidence: int,
        risk_category: str,
        contributions: list[FeatureContribution],
        historical_comparison: dict,
    ) -> dict:
        return {
            "feature_importance_chart": [
                {"feature": item.display_name, "importance": item.importance}
                for item in sorted(contributions, key=lambda item: item.importance, reverse=True)
            ],
            "confidence_gauge": {"value": confidence, "label": f"{confidence}% confidence"},
            "contribution_bars": [
                {"feature": item.display_name, "contribution": item.contribution, "direction": item.direction}
                for item in sorted(contributions, key=lambda item: abs(item.contribution), reverse=True)
            ],
            "risk_breakdown": {
                "risk_score": risk_score,
                "risk_category": risk_category,
                "weather": round(sum(item.contribution for item in contributions if item.influence_group == "weather"), 2),
                "vegetation": round(sum(item.contribution for item in contributions if item.influence_group == "vegetation"), 2),
                "historical": round(sum(item.contribution for item in contributions if item.influence_group == "historical"), 2),
            },
            "historical_comparison_chart": historical_comparison["chart"],
        }

    def _influence_group(self, feature: str) -> str:
        if feature in WEATHER_FEATURES:
            return "weather"
        if feature in VEGETATION_FEATURES:
            return "vegetation"
        if feature in HISTORICAL_FEATURES:
            return "historical"
        return "model"

    def _display_name(self, feature: str) -> str:
        labels = {
            "temperature": "Temperature",
            "humidity": "Humidity",
            "wind_speed": "Wind Speed",
            "rainfall": "Rainfall",
            "ndvi": "NDVI",
            "nbr": "NBR",
            "hotspots": "Recent Hotspots",
            "fire_weather_index": "Fire Weather Risk Index",
        }
        return labels.get(feature, feature.replace("_", " ").title())
