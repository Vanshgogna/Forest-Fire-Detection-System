"""Machine-learning extension points for FireSight."""

from backend.ml.pipeline import FireRiskModelService, PredictionResult
from backend.ml.registry import DEFAULT_MODEL_REGISTRY, ModelAdapter, ModelRegistry

__all__ = [
    "DEFAULT_MODEL_REGISTRY",
    "FireRiskModelService",
    "ModelAdapter",
    "ModelRegistry",
    "PredictionResult",
]
