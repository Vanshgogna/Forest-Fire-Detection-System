import { memo, useMemo } from "react";
import { MapContainer, CircleMarker, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { RegionRisk } from "../../types";
import { getRiskColor, hasProviderData } from "../../utils/risk";
import { useEnvironmentalContext } from "../../contexts/EnvironmentalContext";

function riskText(region: RegionRisk) {
  if (region.riskStatus === "unavailable") return "Live prediction unavailable";
  return `Risk ${region.riskScore}%`;
}

function RiskMapComponent({ regions }: { regions: RegionRisk[] }) {
  const { selectedRegionId, setSelectedRegionId } = useEnvironmentalContext();
  const markers = useMemo(
    () =>
      regions.map((region) => ({
        ...region,
        radius: 10 + (hasProviderData(region.hotspotSource?.status) ? region.hotspots : 0),
        color: region.riskStatus === "unavailable" ? "var(--muted)" : getRiskColor(region.riskLevel)
      })),
    [regions]
  );

  return (
    <div className="map-shell">
      <MapContainer center={[21.5, 79]} zoom={5} scrollWheelZoom className="risk-map">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.map((region) => {
          const isSelected = region.id === selectedRegionId;
          return (
            <CircleMarker
              key={region.id}
              center={region.coordinates}
              radius={isSelected ? region.radius + 6 : region.radius}
              pathOptions={{
                color: region.color,
                fillColor: region.color,
                fillOpacity: isSelected ? 0.58 : 0.36,
                weight: isSelected ? 4 : 2
              }}
              eventHandlers={{ click: () => setSelectedRegionId(region.id) }}
            >
              <Tooltip>
                <strong>{region.name}</strong>
                <br />
                {isSelected ? "Selected region · " : ""}{riskText(region)} · {hasProviderData(region.hotspotSource?.status) ? `${region.hotspots} hotspots` : "hotspots unavailable"}
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}

export const RiskMap = memo(RiskMapComponent);
