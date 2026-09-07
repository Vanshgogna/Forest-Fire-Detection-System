from backend.core.config import get_settings


class AlertEngine:
    def evaluate(self, prediction: dict, weather: dict, vegetation: dict) -> list[dict]:
        settings = get_settings()
        alerts = []
        risk_score = prediction.get("risk_score", 0)
        features = prediction.get("feature_values") or {}
        hotspots = prediction.get("hotspots")
        if hotspots is None:
            hotspots = features.get("hotspots", 0)
        if risk_score >= settings.critical_risk_threshold:
            alerts.append({"severity": "Critical", "title": "Critical wildfire probability", "reason": "Prediction score exceeds response threshold."})
        elif risk_score >= settings.high_risk_threshold:
            alerts.append({"severity": "High", "title": "High wildfire probability", "reason": "Prediction score exceeds monitoring threshold."})
        if hotspots >= 1:
            alerts.append({"severity": "High", "title": "Active hotspot detected", "reason": f"NASA FIRMS reported {hotspots:g} active-fire detection(s) in the selected region."})
        if weather.get("temperature", 0) >= 40 and weather.get("humidity", 100) <= 20:
            alerts.append({"severity": "High", "title": "Extreme fire weather", "reason": "High heat and low humidity detected."})
        if weather.get("wind_speed", 0) >= 35:
            alerts.append({"severity": "High", "title": "Strong wind spread risk", "reason": "Wind speed can accelerate wildfire spread."})
        if vegetation.get("ndvi", 1) < 0.35:
            alerts.append({"severity": "High", "title": "Vegetation stress", "reason": "NDVI indicates dry fuel conditions."})
        if vegetation.get("nbr", 1) < 0.25:
            alerts.append({"severity": "Moderate", "title": "Burn ratio decline", "reason": "NBR indicates stressed or recently burned vegetation."})
        return alerts
