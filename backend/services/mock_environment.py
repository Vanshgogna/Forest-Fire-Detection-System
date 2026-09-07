from dataclasses import dataclass
from typing import Literal

from backend.services.region_registry import get_region_location

RiskLevel = Literal["Low", "Moderate", "High", "Critical"]


@dataclass(frozen=True)
class RegionRisk:
    id: str
    name: str
    state: str
    coordinates: tuple[float, float]
    risk_score: int
    risk_level: RiskLevel
    ndvi: float
    nbr: float
    temperature: int
    humidity: int
    wind_speed: int
    rainfall: float
    hotspots: int
    confidence: int


@dataclass(frozen=True)
class WeatherSnapshot:
    label: str
    temperature: int
    humidity: int
    wind: int
    rainfall: float
    fire_weather_index: int


@dataclass(frozen=True)
class AlertItem:
    id: str
    title: str
    region: str
    severity: RiskLevel
    confidence: int
    status: str
    generated_at: str
    explanation: str
    actions: list[str]


REGIONS = [
    RegionRisk(
        id="r1",
        name="Bandipur Tiger Reserve",
        state="Karnataka",
        coordinates=get_region_location("r1").coordinates,
        risk_score=91,
        risk_level="Critical",
        ndvi=0.31,
        nbr=0.18,
        temperature=29,
        humidity=18,
        wind_speed=24,
        rainfall=0,
        hotspots=18,
        confidence=94,
    ),
    RegionRisk(
        id="r2",
        name="Simlipal Biosphere",
        state="Odisha",
        coordinates=get_region_location("r2").coordinates,
        risk_score=78,
        risk_level="High",
        ndvi=0.42,
        nbr=0.31,
        temperature=36,
        humidity=26,
        wind_speed=18,
        rainfall=1.4,
        hotspots=11,
        confidence=88,
    ),
    RegionRisk(
        id="r3",
        name="Gir Forest",
        state="Gujarat",
        coordinates=get_region_location("r3").coordinates,
        risk_score=63,
        risk_level="Moderate",
        ndvi=0.49,
        nbr=0.38,
        temperature=34,
        humidity=34,
        wind_speed=14,
        rainfall=3.2,
        hotspots=5,
        confidence=81,
    ),
    RegionRisk(
        id="r4",
        name="Kaziranga Landscape",
        state="Assam",
        coordinates=get_region_location("r4").coordinates,
        risk_score=29,
        risk_level="Low",
        ndvi=0.71,
        nbr=0.62,
        temperature=27,
        humidity=68,
        wind_speed=8,
        rainfall=11.8,
        hotspots=1,
        confidence=79,
    ),
]

WEATHER = [
    WeatherSnapshot(label="Now", temperature=29, humidity=24, wind=21, rainfall=0, fire_weather_index=76),
    WeatherSnapshot(label="+3h", temperature=31, humidity=20, wind=24, rainfall=0, fire_weather_index=82),
    WeatherSnapshot(label="+6h", temperature=30, humidity=22, wind=19, rainfall=0.2, fire_weather_index=77),
    WeatherSnapshot(label="+9h", temperature=29, humidity=33, wind=13, rainfall=2.1, fire_weather_index=59),
    WeatherSnapshot(label="+12h", temperature=27, humidity=45, wind=9, rainfall=4.8, fire_weather_index=39),
]

ALERTS = [
    AlertItem(
        id="A-2041",
        title="Critical ignition probability",
        region="Bandipur Tiger Reserve",
        severity="Critical",
        confidence=94,
        status="New",
        generated_at="2026-07-02 11:10",
        explanation="Very low humidity, dry vegetation, and increasing wind have elevated wildfire probability beyond the response threshold.",
        actions=["Notify forest control room", "Deploy patrol team", "Verify MODIS hotspot cluster"],
    ),
    AlertItem(
        id="A-2039",
        title="Rapid vegetation stress detected",
        region="Simlipal Biosphere",
        severity="High",
        confidence=88,
        status="Acknowledged",
        generated_at="2026-07-02 10:45",
        explanation="NDVI decline and rising fire weather index indicate fast drying in the eastern buffer zone.",
        actions=["Inspect watchtower feed", "Prepare local response crew", "Monitor next satellite pass"],
    ),
]


def risk_level(score: int):
    if score >= 85:
        return "Critical"
    if score >= 70:
        return "High"
    if score >= 45:
        return "Moderate"
    return "Low"
