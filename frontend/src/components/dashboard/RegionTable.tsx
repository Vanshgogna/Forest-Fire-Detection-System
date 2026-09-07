import { memo, useMemo } from "react";
import { RegionRisk } from "../../types";
import { getRiskColor } from "../../utils/risk";

function riskLabel(region: RegionRisk) {
  if (region.riskStatus === "unavailable") return "Unavailable";
  return `${region.riskLevel} · ${region.riskScore}`;
}

function hasProviderData(status?: string) {
  return status === "live" || status === "degraded";
}

function RegionTableComponent({ regions }: { regions: RegionRisk[] }) {
  const rows = useMemo(
    () =>
      regions.map((region) => ({
        ...region,
        riskColor: region.riskStatus === "unavailable" ? "var(--muted)" : getRiskColor(region.riskLevel)
      })),
    [regions]
  );

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Region</th>
            <th>Risk</th>
            <th>NDVI</th>
            <th>Temp</th>
            <th>Humidity</th>
            <th>Hotspots</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((region) => (
            <tr key={region.id}>
              <td>
                <strong>{region.name}</strong>
                <span>{region.state}</span>
              </td>
              <td>
                <span className="risk-pill" style={{ background: region.riskColor }}>
                  {riskLabel(region)}
                </span>
              </td>
              <td>{hasProviderData(region.vegetationSource?.status) ? region.ndvi : "Unavailable"}</td>
              <td>{hasProviderData(region.weatherSource?.status) ? `${region.temperature}°C` : "Unavailable"}</td>
              <td>{hasProviderData(region.weatherSource?.status) ? `${region.humidity}%` : "Unavailable"}</td>
              <td>{hasProviderData(region.hotspotSource?.status) ? region.hotspots : "Unavailable"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const RegionTable = memo(RegionTableComponent);
