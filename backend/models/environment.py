from typing import Literal

from pydantic import BaseModel


RiskLevel = Literal["Low", "Moderate", "High", "Critical"]


class RegionRisk(BaseModel):
    id: str
    name: str
    state: str
    coordinates: tuple[float, float]
    risk_score: int
    risk_level: RiskLevel
    ndvi: float
    nbr: float
    temperature: int
    humidity: int
    wind_speed: int
    rainfall: float
    hotspots: int
    confidence: int


class WeatherSnapshot(BaseModel):
    label: str
    temperature: int
    humidity: int
    wind: int
    rainfall: float
    fire_weather_index: int


class PredictionRequest(BaseModel):
    region: str
    temperature: float
    humidity: float
    wind_speed: float
    rainfall: float = 0
    ndvi: float
    nbr: float = 0.45
    hotspots: int
    fire_weather_index: float = 40


class PredictionResponse(BaseModel):
    region: str
    risk_score: int
    risk_level: RiskLevel
    confidence: int
    input_snapshot: dict | None = None
    explanation: str
    explanation_details: dict
    top_contributing_features: list[dict]
    feature_importance: dict[str, float]
    risk_factors: list[str]
    historical_comparison: dict
    weather_influence: list[str]
    vegetation_influence: list[str]
    historical_trend_influence: list[str]
    confidence_explanation: str
    visual_explanations: dict
    interpretability: dict
    recommendation_rationales: list[dict]
    recommendations: list[str]


class AlertItem(BaseModel):
    id: str
    title: str
    region: str
    severity: RiskLevel
    confidence: int
    status: str
    generated_at: str
    explanation: str
    actions: list[str]
