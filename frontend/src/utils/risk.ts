import { MetricSource, RiskLevel } from "../types";

export function getRiskColor(level: RiskLevel) {
  const colors: Record<RiskLevel, string> = {
    Low: "var(--success)",
    Moderate: "var(--warning)",
    High: "var(--orange)",
    Critical: "var(--danger)"
  };
  return colors[level];
}

export function getRiskTone(score: number) {
  if (score >= 85) return "critical";
  if (score >= 70) return "high";
  if (score >= 45) return "moderate";
  return "low";
}

export function formatPercent(value: number) {
  return `${Math.round(value)}%`;
}

export function hasProviderData(status?: MetricSource["status"] | string | null) {
  return status === "live" || status === "degraded";
}

export function isAvailableWeatherDataStatus(status?: MetricSource["dataStatus"] | string | null) {
  return status === "LIVE" || status === "CACHED" || status === "RECENT" || status === "STALE";
}

export function sourceStatusLabel(source?: Pick<MetricSource, "status" | "dataStatus"> | null) {
  if (!source) return "UNAVAILABLE";
  return source.dataStatus ?? (hasProviderData(source.status) ? "LIVE" : "UNAVAILABLE");
}
