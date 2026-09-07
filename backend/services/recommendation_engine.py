class RecommendationEngine:
    def generate(self, risk_score: int, drivers: dict[str, float]) -> list[dict]:
        recommendations = []
        if risk_score >= 85:
            recommendations.append({"priority": 1, "action": "Deploy patrol team", "impact": "High"})
        if drivers.get("wind_speed", 0) > 18:
            recommendations.append({"priority": 2, "action": "Prepare rapid response equipment", "impact": "High"})
        if drivers.get("ndvi", 1) < 0.4:
            recommendations.append({"priority": 3, "action": "Increase satellite refresh frequency", "impact": "Medium"})
        return recommendations or [{"priority": 4, "action": "Continue standard monitoring", "impact": "Low"}]
