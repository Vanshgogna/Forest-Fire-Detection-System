from __future__ import annotations

from dataclasses import dataclass


FEATURE_COLUMNS = ["temperature", "humidity", "wind_speed", "rainfall", "ndvi", "nbr", "hotspots", "fire_weather_index"]

FEATURE_DEFAULTS = {
    "temperature": 30.0,
    "humidity": 45.0,
    "wind_speed": 10.0,
    "rainfall": 0.0,
    "ndvi": 0.55,
    "nbr": 0.45,
    "hotspots": 0.0,
    "fire_weather_index": 40.0,
}

FEATURE_BOUNDS = {
    "temperature": (-20.0, 60.0),
    "humidity": (0.0, 100.0),
    "wind_speed": (0.0, 140.0),
    "rainfall": (0.0, 500.0),
    "ndvi": (-1.0, 1.0),
    "nbr": (-1.0, 1.0),
    "hotspots": (0.0, 1000.0),
    "fire_weather_index": (0.0, 100.0),
}


def _coerce_float(value, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class FireRiskPreprocessor:
    feature_columns: tuple[str, ...] = tuple(FEATURE_COLUMNS)
    defaults: dict[str, float] | None = None
    bounds: dict[str, tuple[float, float]] | None = None
    normalize: bool = True

    def __post_init__(self):
        object.__setattr__(self, "defaults", self.defaults or FEATURE_DEFAULTS)
        object.__setattr__(self, "bounds", self.bounds or FEATURE_BOUNDS)

    def clean_record(self, payload: dict) -> dict[str, float]:
        cleaned = {}
        for feature in self.feature_columns:
            lower, upper = self.bounds[feature]
            value = _coerce_float(payload.get(feature), self.defaults[feature])
            cleaned[feature] = _clamp(value, lower, upper)
        return cleaned

    def transform_record(self, payload: dict) -> list[float]:
        cleaned = self.clean_record(payload)
        return [self._normalize(feature, cleaned[feature]) for feature in self.feature_columns]

    def transform_records(self, payloads: list[dict]) -> list[list[float]]:
        return [self.transform_record(payload) for payload in payloads]

    def feature_map(self, payload: dict) -> dict[str, float]:
        cleaned = self.clean_record(payload)
        if not self.normalize:
            return cleaned
        return {feature: self._normalize(feature, value) for feature, value in cleaned.items()}

    def to_dict(self) -> dict:
        return {
            "feature_columns": list(self.feature_columns),
            "defaults": self.defaults,
            "bounds": self.bounds,
            "normalize": self.normalize,
        }

    @classmethod
    def from_dict(cls, payload: dict):
        bounds = {key: tuple(value) for key, value in payload.get("bounds", FEATURE_BOUNDS).items()}
        return cls(
            feature_columns=tuple(payload.get("feature_columns", FEATURE_COLUMNS)),
            defaults=payload.get("defaults", FEATURE_DEFAULTS),
            bounds=bounds,
            normalize=payload.get("normalize", True),
        )

    def _normalize(self, feature: str, value: float) -> float:
        if not self.normalize:
            return value
        lower, upper = self.bounds[feature]
        if upper == lower:
            return 0.0
        return round((value - lower) / (upper - lower), 6)


def build_fire_risk_features(payload: dict) -> dict[str, float]:
    return FireRiskPreprocessor(normalize=False).clean_record(payload)
