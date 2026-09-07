# ML Workflow

## Problem Statement

FireSight AI predicts wildfire risk from weather, vegetation, hotspot, and fire-weather signals. The model produces a risk category, risk score, confidence, feature importance, explanation, visual explanation payloads, and response recommendations. Predictions must never be returned without an explanation.

## Input Features

- `temperature`
- `humidity`
- `wind_speed`
- `rainfall`
- `ndvi`
- `nbr`
- `hotspots`
- `fire_weather_index`

## Output Labels

- `Low`
- `Moderate`
- `High`
- `Critical`

## Preprocessing

The same `FireRiskPreprocessor` is used during training and inference.

Pipeline:

1. Coerce input values to numeric values.
2. Replace missing or invalid values with domain defaults.
3. Clip values to physical and operational bounds.
4. Apply min-max normalization using persisted bounds.

## Training Pipeline

1. Collect weather, vegetation, hotspot, and historical fire data.
2. Clean and normalize records with the shared preprocessor.
3. Train Random Forest as the baseline model.
4. Optionally compare XGBoost with label encoding.
5. Validate with up to 5-fold cross-validation.
6. Evaluate accuracy, macro precision, macro recall, and macro F1.
7. Serialize a Joblib bundle containing the model, preprocessor, feature schema, labels, algorithm, metrics, and version.

## Prediction Pipeline

1. Load the model bundle when an artifact is available.
2. Apply the stored preprocessor to incoming records.
3. Generate single or batch predictions.
4. Estimate confidence from model probabilities when available.
5. Generate structured explainability details.
6. Return feature importance, top contributors, grouped weather/vegetation/historical influence, confidence rationale, visual explanation data, and recommendations.

If no trained artifact is loaded, the service uses the same cleaned feature map with a deterministic domain heuristic so the application remains operable during local development.

## Explainability Contract

See [Explainable AI](explainable-ai.md) for the full transparency contract. The prediction service enforces this contract by constructing `explanation_details` before returning a prediction.
