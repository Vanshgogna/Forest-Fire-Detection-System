from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from statistics import mean
import time
from typing import Any

try:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder
except Exception:  # pragma: no cover - optional runtime dependencies in scaffold mode
    joblib = None
    RandomForestClassifier = None
    cross_val_score = None
    accuracy_score = f1_score = precision_score = recall_score = None
    LabelEncoder = None

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - xgboost is optional
    XGBClassifier = None

from backend.ml.explainability import FireRiskExplanationEngine
from backend.ml.features import FEATURE_COLUMNS, FireRiskPreprocessor, build_fire_risk_features
from backend.ml.registry import DEFAULT_MODEL_REGISTRY, ModelRegistry
from backend.services.observability import observability_registry

logger = logging.getLogger("firesight.ml")


@dataclass
class PredictionResult:
    risk_score: int
    risk_category: str
    confidence: int
    feature_importance: dict[str, float]
    explanation: str
    explanation_details: dict
    recommendations: list[str]

    def __post_init__(self) -> None:
        if not self.explanation or not self.explanation_details:
            raise ValueError("AI predictions must include an explanation")
        required = ["why", "top_contributing_features", "confidence_explanation", "visual_explanations", "recommendation_rationales"]
        missing = [field for field in required if not self.explanation_details.get(field)]
        if missing:
            raise ValueError(f"AI prediction explanation is missing required fields: {', '.join(missing)}")


@dataclass
class ModelBundle:
    model: Any
    preprocessor: FireRiskPreprocessor
    algorithm: str
    version: str
    metrics: dict[str, float]
    label_encoder: Any | None = None


class FireRiskModelService:
    model_version = "fire-risk-v1.3"
    feature_columns = FEATURE_COLUMNS

    def __init__(self, artifact_path: str | None = None, model_registry: ModelRegistry | None = None):
        self.preprocessor = FireRiskPreprocessor()
        self.model = None
        self.label_encoder = None
        self.algorithm = "heuristic"
        self.explanation_engine = FireRiskExplanationEngine()
        self.model_registry = model_registry or DEFAULT_MODEL_REGISTRY
        if artifact_path:
            self.load(artifact_path)

    def predict(self, payload: dict) -> PredictionResult:
        started = time.perf_counter()
        features = build_fire_risk_features(payload)
        if self.model is not None:
            category, confidence = self._model_prediction(payload)
            score = self._score_from_category(category)
        else:
            score = self._heuristic_score(features)
            category = self._category(score)
            confidence = self._heuristic_confidence(score, features)
        feature_importance = self._feature_importance()
        recommendations = self._recommendations(score)
        explanation_details = self.explanation_engine.explain(
            features=features,
            risk_score=score,
            risk_category=category,
            confidence=confidence,
            feature_importance=feature_importance,
            recommendations=recommendations,
        )
        result = PredictionResult(
            risk_score=score,
            risk_category=category,
            confidence=confidence,
            feature_importance=feature_importance,
            explanation=explanation_details.why,
            explanation_details=explanation_details.to_dict(),
            recommendations=recommendations,
        )
        logger.info(
            "model_prediction_completed version=%s algorithm=%s risk_category=%s risk_score=%s confidence=%s",
            self.model_version,
            self.algorithm,
            result.risk_category,
            result.risk_score,
            result.confidence,
        )
        observability_registry.record_prediction(
            risk_category=result.risk_category,
            confidence=result.confidence,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            model_version=self.model_version,
        )
        return result

    def batch_predict(self, payloads: list[dict]) -> list[PredictionResult]:
        logger.info("model_batch_prediction_started count=%s version=%s", len(payloads), self.model_version)
        return [self.predict(payload) for payload in payloads]

    def train(self, dataframe, target_column: str = "risk_class", algorithm: str = "random_forest", persist_model: bool = True) -> dict:
        if RandomForestClassifier is None:
            logger.warning("model_training_skipped reason=missing_scikit_learn algorithm=%s", algorithm)
            return {"status": "skipped", "reason": "scikit-learn is not installed"}
        if target_column not in dataframe.columns:
            logger.warning("model_training_failed reason=missing_target target_column=%s algorithm=%s", target_column, algorithm)
            return {"status": "failed", "reason": f"Missing target column: {target_column}"}

        logger.info("model_training_started algorithm=%s target_column=%s rows=%s", algorithm, target_column, len(dataframe))
        records = dataframe.drop(columns=[target_column]).to_dict(orient="records")
        X = self.preprocessor.transform_records(records)
        y = list(dataframe[target_column])
        model = self._build_model(algorithm)
        if model is None:
            return {"status": "skipped", "reason": f"{algorithm} is not installed"}
        training_labels = self._encode_labels(y, algorithm)

        cv_folds = min(5, len(y))
        scores = cross_val_score(model, X, training_labels, cv=cv_folds) if cv_folds >= 2 else []
        model.fit(X, training_labels)
        predictions = self._decode_labels(model.predict(X))
        metrics = self._metrics(y, predictions)

        self.model = model
        self.algorithm = algorithm
        artifact_path = self.save(algorithm, metrics) if persist_model else None
        logger.info("model_training_completed algorithm=%s version=%s persisted=%s", algorithm, self.model_version, bool(artifact_path))
        return {
            "status": "trained",
            "algorithm": algorithm,
            "version": self.model_version,
            "artifact_path": artifact_path,
            "cv_accuracy": float(mean(scores)) if len(scores) else None,
            "metrics": metrics,
            "feature_schema": {"columns": self.feature_columns, "target": target_column},
            "preprocessing": self.preprocessor.to_dict(),
        }

    def save(self, algorithm: str | None = None, metrics: dict[str, float] | None = None) -> str | None:
        if joblib is None or self.model is None:
            logger.warning("model_save_skipped reason=missing_joblib_or_model algorithm=%s", algorithm or self.algorithm)
            return None
        artifact_path = self._artifact_path(algorithm or self.algorithm)
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        bundle = ModelBundle(
            model=self.model,
            preprocessor=self.preprocessor,
            algorithm=algorithm or self.algorithm,
            version=self.model_version,
            metrics=metrics or {},
            label_encoder=self.label_encoder,
        )
        joblib.dump(bundle, artifact_path)
        logger.info("model_artifact_saved algorithm=%s version=%s", algorithm or self.algorithm, self.model_version)
        return artifact_path

    def load(self, artifact_path: str):
        if joblib is None:
            logger.error("model_artifact_load_failed reason=missing_joblib")
            raise RuntimeError("joblib is required to load model artifacts")
        bundle = joblib.load(artifact_path)
        self.model = bundle.model
        self.preprocessor = bundle.preprocessor
        self.algorithm = bundle.algorithm
        self.model_version = bundle.version
        self.label_encoder = getattr(bundle, "label_encoder", None)
        logger.info("model_artifact_loaded algorithm=%s version=%s", self.algorithm, self.model_version)
        return self

    def retrain(self, dataframe, target_column: str = "risk_class", algorithm: str = "random_forest") -> dict:
        return self.train(dataframe=dataframe, target_column=target_column, algorithm=algorithm, persist_model=True)

    def training_plan(self, algorithm: str, target_column: str, tune_hyperparameters: bool, persist_model: bool) -> dict:
        return {
            "status": "ready",
            "problem_statement": "Classify wildfire risk from weather, vegetation, hotspot, and fire-weather signals.",
            "input_features": self.feature_columns,
            "output_labels": ["Low", "Moderate", "High", "Critical"],
            "feature_engineering": ["numeric_coercion", "domain_defaults", "range_clipping", "min_max_normalization"],
            "data_cleaning": "Missing and invalid values are replaced with domain defaults before range clipping.",
            "missing_value_handling": self.preprocessor.defaults,
            "normalization": "Min-max normalization with persisted domain bounds.",
            "categorical_encoding": "Risk labels are treated as supervised class labels.",
            "data_splitting": "Cross-validation is used for small and medium tabular datasets.",
            "validation_strategy": "Cross-validation plus in-sample metrics for model registry metadata.",
            "cross_validation": "Up to 5 folds, capped by available sample count.",
            "hyperparameter_tuning": "grid_search_enabled" if tune_hyperparameters else "default_enterprise_baseline",
            "evaluation_metrics": ["accuracy", "precision_macro", "recall_macro", "f1_macro"],
            "model_serialization": "joblib bundle containing model and preprocessing configuration" if persist_model else "disabled",
            "prediction_pipeline": "clean -> clip -> normalize -> predict -> confidence -> explain -> recommend",
            "algorithm": algorithm,
            "model_adapter": self.model_registry.get(algorithm).to_dict() if self.model_registry.get(algorithm) else None,
            "model_extensibility": {
                "stable_prediction_api": True,
                "available_adapters": self.model_registry.trainable_algorithms(),
                "future_adapters": self.model_registry.future_algorithms(),
                "registry": self.model_registry.to_dict(),
            },
            "target_column": target_column,
            "model_registry": {"artifact_dir": self._artifact_dir(), "version": self.model_version},
        }

    def _model_prediction(self, payload: dict) -> tuple[str, int]:
        transformed = [self.preprocessor.transform_record(payload)]
        category = str(self._decode_labels(self.model.predict(transformed))[0])
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(transformed)[0]
            return category, int(round(max(probabilities) * 100))
        return category, 80

    def _build_model(self, algorithm: str):
        adapter = self.model_registry.get(algorithm)
        if adapter is None or adapter.status != "available" or not adapter.supports_training:
            logger.warning("model_build_skipped reason=unsupported_adapter algorithm=%s", algorithm)
            return None
        if algorithm == "xgboost":
            if XGBClassifier is None:
                return None
            return XGBClassifier(n_estimators=250, max_depth=6, learning_rate=0.05, random_state=42)
        return RandomForestClassifier(n_estimators=250, max_depth=12, min_samples_leaf=2, random_state=42)

    def _encode_labels(self, labels: list, algorithm: str):
        if algorithm != "xgboost":
            self.label_encoder = None
            return labels
        if LabelEncoder is None:
            return labels
        self.label_encoder = LabelEncoder()
        return self.label_encoder.fit_transform(labels)

    def _decode_labels(self, labels):
        if self.label_encoder is None:
            return labels
        return self.label_encoder.inverse_transform(labels)

    def _artifact_path(self, algorithm: str) -> str:
        artifact_dir = Path(self._artifact_dir())
        return str(artifact_dir / f"fire_risk_{algorithm}_{self.model_version}.joblib")

    def _artifact_dir(self) -> str:
        try:
            from backend.core.config import get_settings

            return get_settings().model_artifact_dir
        except Exception:
            return "backend/artifacts/models"

    def _metrics(self, y_true, y_pred) -> dict[str, float]:
        if accuracy_score is None:
            return {}
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
            "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
            "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        }

    def _feature_importance(self) -> dict[str, float]:
        if self.model is not None and hasattr(self.model, "feature_importances_"):
            values = [float(value) for value in self.model.feature_importances_]
            total = sum(values) or 1.0
            return {feature: round(value / total, 4) for feature, value in zip(self.feature_columns, values, strict=False)}
        return {
            "temperature": 0.25,
            "humidity": 0.22,
            "wind_speed": 0.15,
            "rainfall": 0.07,
            "ndvi": 0.13,
            "nbr": 0.1,
            "hotspots": 0.05,
            "fire_weather_index": 0.03,
        }

    def _heuristic_score(self, features: dict[str, float]) -> int:
        heat = min(30, features["temperature"] * 0.75)
        dryness = min(30, (100 - features["humidity"]) * 0.32)
        wind = min(18, features["wind_speed"] * 0.65)
        vegetation = min(16, (1 - features["ndvi"]) * 18 + (1 - features["nbr"]) * 8)
        hotspots = min(12, features["hotspots"] * 2.2)
        fwi_pressure = min(8, features["fire_weather_index"] * 0.08)
        rain_relief = min(18, features["rainfall"] * 2.5)
        return max(0, min(100, round(heat + dryness + wind + vegetation + hotspots + fwi_pressure - rain_relief)))

    def _heuristic_confidence(self, score: int, features: dict[str, float]) -> int:
        signal_count = sum(1 for value in features.values() if value is not None)
        base = 72 + min(18, signal_count * 2)
        category_boost = 4 if score >= 70 or score < 30 else 0
        return max(60, min(96, base + category_boost))

    def _category(self, score: int) -> str:
        if score >= 85:
            return "Critical"
        if score >= 70:
            return "High"
        if score >= 45:
            return "Moderate"
        return "Low"

    def _score_from_category(self, category: str) -> int:
        return {"Critical": 92, "High": 78, "Moderate": 58, "Low": 28}.get(category, 50)

    def _explain(self, features: dict[str, float], category: str) -> str:
        drivers = sorted(self._feature_importance().items(), key=lambda item: item[1], reverse=True)[:3]
        driver_text = ", ".join(feature.replace("_", " ") for feature, _ in drivers)
        return f"Wildfire risk is {category}. The leading model drivers are {driver_text}, combined with current fuel and weather conditions."

    def _recommendations(self, score: int) -> list[str]:
        if score >= 85:
            return ["Deploy patrol teams", "Prepare firefighting equipment", "Increase satellite refresh frequency"]
        if score >= 70:
            return ["Monitor hourly", "Verify hotspots", "Prepare local response crew"]
        if score >= 45:
            return ["Review forecast", "Inspect dry fuel zones", "Maintain readiness posture"]
        return ["Continue monitoring", "Maintain standard patrols", "Refresh weather data on schedule"]
