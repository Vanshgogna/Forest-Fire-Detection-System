import { RegionRisk, WeatherSnapshot } from "../types";
import { hasProviderData } from "./risk";

export function safeFileNamePart(value: string) {
  return value
    .trim()
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "export";
}

export function downloadTextFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function htmlEscape(value: unknown) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function csvValue(value: unknown) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function buildRegionsCsv(regions: RegionRisk[], weatherData: WeatherSnapshot[]) {
  const averageFwi = weatherData.length
    ? Math.round(weatherData.reduce((sum, item) => sum + item.fireWeatherIndex, 0) / weatherData.length)
    : "";
  const rows = [
    ["Region", "State", "Risk Score", "Risk Level", "Confidence", "Temperature", "Humidity", "Wind Speed", "Rainfall", "NDVI", "NBR", "Hotspots", "Weather Status", "Vegetation Status", "Hotspot Status", "Average FWI"],
    ...regions.map((region) => [
      region.name,
      region.state,
      region.riskStatus === "unavailable" ? "Unavailable" : region.riskScore,
      region.riskStatus === "unavailable" ? "Unavailable" : region.riskLevel,
      region.riskStatus === "unavailable" ? "Unavailable" : region.confidence,
      region.temperature,
      region.humidity,
      region.windSpeed,
      region.rainfall,
      hasProviderData(region.vegetationSource?.status) ? region.ndvi : "Unavailable",
      region.riskStatus === "unavailable" ? "Unavailable" : region.nbr,
      hasProviderData(region.hotspotSource?.status) ? region.hotspots : "Unavailable",
      region.weatherSource?.dataStatus ?? "UNAVAILABLE",
      region.vegetationSource?.dataStatus ?? "UNAVAILABLE",
      region.hotspotSource?.dataStatus ?? "UNAVAILABLE",
      averageFwi
    ])
  ];
  return rows.map((row) => row.map(csvValue).join(",")).join("\n");
}

export function buildRegionsGeoJson(regions: RegionRisk[]) {
  return JSON.stringify({
    type: "FeatureCollection",
    features: regions.map((region) => ({
      type: "Feature",
      properties: {
        id: region.id,
        name: region.name,
        state: region.state,
        riskScore: region.riskStatus === "unavailable" ? null : region.riskScore,
        riskLevel: region.riskStatus === "unavailable" ? null : region.riskLevel,
        confidence: region.riskStatus === "unavailable" ? null : region.confidence,
        ndvi: hasProviderData(region.vegetationSource?.status) ? region.ndvi : null,
        nbr: region.riskStatus === "unavailable" ? null : region.nbr,
        hotspots: hasProviderData(region.hotspotSource?.status) ? region.hotspots : null,
        weatherStatus: region.weatherSource?.dataStatus ?? "UNAVAILABLE",
        vegetationStatus: region.vegetationSource?.dataStatus ?? "UNAVAILABLE",
        hotspotStatus: region.hotspotSource?.dataStatus ?? "UNAVAILABLE"
      },
      geometry: {
        type: "Point",
        coordinates: [region.coordinates[1], region.coordinates[0]]
      }
    }))
  }, null, 2);
}
