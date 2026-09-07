from backend.ml.features import FireRiskPreprocessor
from backend.ml.pipeline import FireRiskModelService
from backend.ml.registry import DEFAULT_MODEL_REGISTRY


def test_preprocessor_handles_missing_invalid_and_out_of_range_values():
    preprocessor = FireRiskPreprocessor()
    cleaned = preprocessor.clean_record({"temperature": "bad", "humidity": 250, "ndvi": None})

    assert cleaned["temperature"] == preprocessor.defaults["temperature"]
    assert cleaned["humidity"] == 100.0
    assert cleaned["ndvi"] == preprocessor.defaults["ndvi"]


def test_preprocessor_serialization_round_trip_keeps_inference_consistent():
    preprocessor = FireRiskPreprocessor()
    restored = FireRiskPreprocessor.from_dict(preprocessor.to_dict())
    payload = {"temperature": 40, "humidity": 18, "wind_speed": 30, "rainfall": 0, "ndvi": 0.25, "nbr": 0.2, "hotspots": 12}

    assert restored.transform_record(payload) == preprocessor.transform_record(payload)


def test_model_service_supports_single_and_batch_prediction_contracts():
    service = FireRiskModelService()
    payload = {"temperature": 40, "humidity": 18, "wind_speed": 30, "rainfall": 0, "ndvi": 0.25, "nbr": 0.2, "hotspots": 12}

    single = service.predict(payload)
    batch = service.batch_predict([payload, payload])

    assert single.risk_category in {"Low", "Moderate", "High", "Critical"}
    assert 0 <= single.risk_score <= 100
    assert 0 <= single.confidence <= 100
    assert len(batch) == 2
    assert "temperature" in single.feature_importance
    assert single.explanation
    assert single.explanation_details["why"]
    assert single.explanation_details["top_contributing_features"]
    assert single.explanation_details["weather_influence"]
    assert single.explanation_details["vegetation_influence"]
    assert single.explanation_details["historical_comparison"]
    assert single.explanation_details["confidence_explanation"]
    assert "feature_importance_chart" in single.explanation_details["visual_explanations"]
    assert "confidence_gauge" in single.explanation_details["visual_explanations"]
    assert "contribution_bars" in single.explanation_details["visual_explanations"]
    assert "risk_breakdown" in single.explanation_details["visual_explanations"]
    assert "SHAP" in single.explanation_details["interpretability"]["future_methods"]


def test_training_plan_discloses_required_ml_engineering_contract():
    plan = FireRiskModelService().training_plan(
        algorithm="random_forest",
        target_column="risk_class",
        tune_hyperparameters=False,
        persist_model=True,
    )

    assert "problem_statement" in plan
    assert "input_features" in plan
    assert "evaluation_metrics" in plan
    assert "model_serialization" in plan
    assert plan["model_extensibility"]["stable_prediction_api"] is True
    assert "random_forest" in plan["model_extensibility"]["available_adapters"]
    assert "satellite_cnn" in plan["model_extensibility"]["future_adapters"]


def test_model_registry_allows_future_models_without_prediction_api_changes():
    registry = DEFAULT_MODEL_REGISTRY

    assert "random_forest" in registry.trainable_algorithms()
    assert "multimodal_fusion" in registry.future_algorithms()
    assert registry.require("satellite_cnn").artifact_suffix == "onnx"

    service = FireRiskModelService(model_registry=registry)
    payload = {"temperature": 35, "humidity": 30, "wind_speed": 12, "rainfall": 1, "ndvi": 0.4, "nbr": 0.3, "hotspots": 4}
    prediction = service.predict(payload)

    assert prediction.explanation_details["interpretability"]["black_box_policy"]
