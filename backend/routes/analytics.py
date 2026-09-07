from fastapi import APIRouter

from backend.services.mock_environment import REGIONS

router = APIRouter()


@router.get("/summary")
def get_analytics_summary():
    total_hotspots = sum(region.hotspots for region in REGIONS)
    average_risk = round(sum(region.risk_score for region in REGIONS) / len(REGIONS))
    average_confidence = round(sum(region.confidence for region in REGIONS) / len(REGIONS))
    high_risk_regions = [region for region in REGIONS if region.risk_score >= 70]

    return {
        "overall_fire_risk": average_risk,
        "active_hotspots": total_hotspots,
        "average_prediction_confidence": average_confidence,
        "high_risk_regions": len(high_risk_regions),
        "satellite_coverage": 97,
        "source_type": "simulated_development_fixture",
        "message": "Analytics currently combine live weather with development fixture risk, vegetation, and hotspot data.",
    }
