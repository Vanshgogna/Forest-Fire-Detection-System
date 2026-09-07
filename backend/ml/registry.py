from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelAdapter:
    """Metadata contract for pluggable fire-risk model implementations."""

    name: str
    display_name: str
    family: str
    status: str
    supports_training: bool
    supports_predict_proba: bool
    explanation_methods: list[str]
    artifact_suffix: str = "joblib"

    def to_dict(self) -> dict:
        return asdict(self)


class ModelRegistry:
    """Registry that lets new models be added without changing prediction APIs."""

    def __init__(self, adapters: list[ModelAdapter] | None = None):
        self._adapters: dict[str, ModelAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: ModelAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ModelAdapter | None:
        return self._adapters.get(name)

    def require(self, name: str) -> ModelAdapter:
        adapter = self.get(name)
        if adapter is None:
            raise ValueError(f"Unsupported model adapter: {name}")
        return adapter

    def supported_algorithms(self) -> list[str]:
        return sorted(self._adapters)

    def trainable_algorithms(self) -> list[str]:
        return sorted(name for name, adapter in self._adapters.items() if adapter.supports_training and adapter.status == "available")

    def future_algorithms(self) -> list[str]:
        return sorted(name for name, adapter in self._adapters.items() if adapter.status == "future")

    def to_dict(self) -> dict:
        return {name: adapter.to_dict() for name, adapter in sorted(self._adapters.items())}


DEFAULT_MODEL_REGISTRY = ModelRegistry(
    [
        ModelAdapter(
            name="heuristic",
            display_name="Domain Heuristic Baseline",
            family="rules",
            status="available",
            supports_training=False,
            supports_predict_proba=False,
            explanation_methods=["domain_contributions", "feature_importance"],
        ),
        ModelAdapter(
            name="random_forest",
            display_name="Random Forest Fire-Risk Classifier",
            family="tree_ensemble",
            status="available",
            supports_training=True,
            supports_predict_proba=True,
            explanation_methods=["feature_importance", "permutation_importance", "SHAP"],
        ),
        ModelAdapter(
            name="xgboost",
            display_name="XGBoost Fire-Risk Classifier",
            family="gradient_boosting",
            status="available",
            supports_training=True,
            supports_predict_proba=True,
            explanation_methods=["feature_importance", "SHAP", "partial_dependence"],
        ),
        ModelAdapter(
            name="satellite_cnn",
            display_name="Satellite Raster Deep Learning Model",
            family="deep_learning",
            status="future",
            supports_training=True,
            supports_predict_proba=True,
            explanation_methods=["Grad-CAM", "SHAP", "saliency_maps"],
            artifact_suffix="onnx",
        ),
        ModelAdapter(
            name="multimodal_fusion",
            display_name="Weather, Raster, Hotspot, and History Fusion Model",
            family="multimodal",
            status="future",
            supports_training=True,
            supports_predict_proba=True,
            explanation_methods=["SHAP", "attention_maps", "partial_dependence"],
            artifact_suffix="onnx",
        ),
    ]
)
