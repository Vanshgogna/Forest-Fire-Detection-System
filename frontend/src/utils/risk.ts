import { RiskLevel } from "../types";

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
