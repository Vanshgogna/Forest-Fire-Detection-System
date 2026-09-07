from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionLocation:
    id: str
    name: str
    state: str
    latitude: float
    longitude: float
    timezone: str
    coordinate_method: str
    database_id: int
    monitoring_radius_degrees: float = 0.5
    crs: str = "EPSG:4326"

    @property
    def coordinates(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)

    def bounding_box(self, buffer_degrees: float | None = None) -> tuple[float, float, float, float]:
        radius = buffer_degrees if buffer_degrees is not None else self.monitoring_radius_degrees
        west = max(-180.0, self.longitude - radius)
        south = max(-90.0, self.latitude - radius)
        east = min(180.0, self.longitude + radius)
        north = min(90.0, self.latitude + radius)
        return (west, south, east, north)

    def as_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.id,
            "region": self.name,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "coordinate_method": self.coordinate_method,
            "database_id": self.database_id,
            "monitoring_radius_degrees": self.monitoring_radius_degrees,
            "bounding_box": self.bounding_box(),
            "crs": self.crs,
        }


REGION_LOCATIONS = [
    RegionLocation(
        id="r1",
        name="Bandipur Tiger Reserve",
        state="Karnataka",
        latitude=11.667,
        longitude=76.629,
        timezone="Asia/Kolkata",
        coordinate_method="configured representative point",
        database_id=1,
    ),
    RegionLocation(
        id="r2",
        name="Simlipal Biosphere",
        state="Odisha",
        latitude=21.594,
        longitude=86.335,
        timezone="Asia/Kolkata",
        coordinate_method="configured representative point",
        database_id=2,
    ),
    RegionLocation(
        id="r3",
        name="Gir Forest",
        state="Gujarat",
        latitude=21.124,
        longitude=70.824,
        timezone="Asia/Kolkata",
        coordinate_method="configured representative point",
        database_id=3,
    ),
    RegionLocation(
        id="r4",
        name="Kaziranga Landscape",
        state="Assam",
        latitude=26.577,
        longitude=93.171,
        timezone="Asia/Kolkata",
        coordinate_method="configured representative point",
        database_id=4,
    ),
]


def get_region_location(region_id: str | None = None) -> RegionLocation:
    selected_id = region_id or "r1"
    region = next((item for item in REGION_LOCATIONS if item.id == selected_id), None)
    if not region:
        valid = ", ".join(item.id for item in REGION_LOCATIONS)
        raise ValueError(f"Unknown region_id. Expected one of: {valid}")
    return region


def list_region_locations() -> list[RegionLocation]:
    return list(REGION_LOCATIONS)
