# Explainable AI

FireSight predictions must never be returned as black-box scores. Every prediction includes a human-readable explanation, confidence rationale, contributing features, risk factors, recommendation rationales, and chart-ready explanation data.

## Prediction Contract

Every single, batch, and explainability sample prediction includes:

- Prediction risk class.
- Risk score.
- Confidence score.
- Explanation of why the model predicted the result.
- Top contributing features.
- Full feature importance.
- Weather influence.
- Vegetation-index influence.
- Historical trend influence.
- Historical comparison.
- Risk factors.
- Recommendation rationales.
- Visual explanation payloads.
- Future interpretability integration metadata.

## Explanation Engine

`FireRiskExplanationEngine` creates structured explanations from the same cleaned feature values used by the model pipeline.

For every prediction it explains:

- Why the model predicted the result.
- Which weather variables influenced it: temperature, humidity, wind speed, rainfall, and fire weather index.
- Which vegetation indices influenced it: NDVI and NBR.
- Which historical signals influenced it: recent hotspot pressure and historical seasonal average comparison.
- How confident the model is and why.

## Visual Explanations

The API returns chart-ready data for:

- Feature importance charts.
- Confidence gauges.
- Contribution bars.
- Risk breakdown by weather, vegetation, and historical signals.
- Historical comparison charts.

The frontend explainability dashboard can render these as feature bars, confidence gauges, contribution charts, risk breakdown panels, and historical comparison views.

## Interpretability Roadmap

Current implementation:

- Domain heuristic contribution scoring.
- Model `feature_importances_` when a trained tree model is loaded.
- Human-readable recommendation rationales.

Future integrations:

- SHAP for local and global additive explanations.
- LIME for local surrogate explanations.
- Permutation importance for model-agnostic global importance.
- Partial dependence plots for directional feature sensitivity.

## User Trust Rules

- Never show only a score.
- Always explain the strongest drivers in operational language.
- Always include confidence and confidence rationale.
- Always explain why recommendations are useful.
- Avoid black-box phrasing such as "the model says so."
- Preserve uncertainty and limitations where confidence is lower.
