import { motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  ArrowRight,
  BrainCircuit,
  Leaf,
  MapPin,
  RefreshCcw,
  Wind
} from "lucide-react";
import { Link } from "react-router-dom";
import { ENVIRONMENTAL_QUERY_KEY } from "../../hooks/useEnvironmentalData";
import { RegionRisk, TrendPoint } from "../../types";
import { hasProviderData } from "../../utils/risk";

interface PredictionSummaryProps {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherSource?: RegionRisk["weatherSource"];
}

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function hasPrediction(region: RegionRisk) {
  return region.riskStatus !== "unavailable";
}

function hasVegetation(region: RegionRisk) {
  return hasProviderData(region.vegetationSource?.status);
}

function riskText(region: RegionRisk) {
  return hasPrediction(region) ? `${region.riskScore}` : "Unavailable";
}

export function PredictionSummary({ regions, trendData, weatherSource }: PredictionSummaryProps) {
  const queryClient = useQueryClient();
  const summary = useMemo(() => {
    const predictedRegions = regions.filter(hasPrediction);
    const liveVegetationRegions = regions.filter(hasVegetation);
    const rankedRegions = [...regions].sort((a, b) => (hasPrediction(b) ? b.riskScore : -1) - (hasPrediction(a) ? a.riskScore : -1));
    return {
      rankedRegions,
      highestRiskRegion: rankedRegions[0],
      overallRisk: predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.riskScore))) : null,
      confidence: predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.confidence))) : null,
      avgNdvi: liveVegetationRegions.length ? average(liveVegetationRegions.map((region) => region.ndvi)).toFixed(2) : null
    };
  }, [regions]);
  const { highestRiskRegion, overallRisk, confidence, avgNdvi } = summary;
  const weatherAvailable = hasProviderData(highestRiskRegion.weatherSource?.status ?? weatherSource?.status);
  const weatherSourceDetail = weatherSource?.message ?? weatherSource?.provider ?? "source unavailable";
  const riskSourceDetail = highestRiskRegion.riskSource?.message ?? "Live prediction unavailable";
  const previousRisk = trendData[trendData.length - 2]?.risk ?? overallRisk;
  const latestRisk = trendData[trendData.length - 1]?.risk ?? overallRisk;
  const trendDelta = overallRisk === null || previousRisk === null || latestRisk === null ? 0 : latestRisk - previousRisk;
  const priorityAction = !hasPrediction(highestRiskRegion)
    ? `Monitor ${highestRiskRegion.name} as live prediction data becomes available.`
    : hasProviderData(highestRiskRegion.hotspotSource?.status) && highestRiskRegion.hotspots > 0
      ? `Verify ${highestRiskRegion.hotspots} active hotspot${highestRiskRegion.hotspots === 1 ? "" : "s"} in ${highestRiskRegion.name} and keep response teams on standby.`
      : `Monitor ${highestRiskRegion.name} and keep response teams ready for changing weather conditions.`;
  const gaugeStyle = useMemo(
    () => ({
      background: `conic-gradient(#e53935 ${(overallRisk ?? 0) * 3.6}deg, color-mix(in srgb, var(--border) 70%, transparent) 0deg)`
    }),
    [overallRisk]
  );

  return (
    <motion.section
      className="prediction-summary"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      aria-labelledby="prediction-summary-title"
    >
      <header className="prediction-summary-header">
        <div>
          <span className="eyebrow">Central Intelligence Panel</span>
          <h2 id="prediction-summary-title">
            <BrainCircuit size={28} /> AI Prediction Summary
          </h2>
          <p>Focused wildfire risk assessment for the current operating window. Weather: {weatherSourceDetail}.</p>
        </div>
        <div className="prediction-summary-actions">
          <span>{weatherSourceDetail}</span>
          <span>{weatherSource?.provider ?? "weather source"}</span>
          <button
            className="button secondary"
            type="button"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY })}
          >
            <RefreshCcw size={16} /> Refresh Prediction
          </button>
        </div>
      </header>

      <div className="prediction-summary-grid">
        <article className="executive-risk-card">
          <div className="risk-card-bg" />
          <div className="risk-card-content">
            <div>
              <span>Overall Risk Level</span>
              <strong>{overallRisk === null ? "UNAVAILABLE" : highestRiskRegion.riskLevel.toUpperCase()}</strong>
              <p>{riskSourceDetail}</p>
            </div>
            <div className="risk-gauge" style={gaugeStyle} aria-label={overallRisk === null ? "Live prediction unavailable" : `Overall risk score ${overallRisk} out of 100`}>
              <div>
                <strong>{overallRisk ?? "--"}</strong>
                <span>{overallRisk === null ? "risk" : "/100"}</span>
              </div>
            </div>
          </div>
          <div className="risk-card-footer">
            <span>{overallRisk === null ? "No live risk trend" : `Risk trend ▲ +${Math.max(trendDelta, 0)}% compared to yesterday`}</span>
            <span>{highestRiskRegion.riskStatus === "live" ? "Live ML" : highestRiskRegion.riskStatus === "simulation" ? "Simulation" : "Unavailable"}</span>
          </div>
        </article>

        <article className="highest-region-card">
          <div className="highest-region-map">
            <MapPin size={28} />
          </div>
          <div>
            <span>Highest Risk Region</span>
            <h3>{highestRiskRegion.name}</h3>
            <div className="highest-region-metrics">
              <span>Risk {riskText(highestRiskRegion)}</span>
              <span>Confidence {hasPrediction(highestRiskRegion) ? `${highestRiskRegion.confidence}%` : "Unavailable"}</span>
            </div>
            <Link className="button secondary" to="/map">Open GIS Map <ArrowRight size={16} /></Link>
          </div>
        </article>

        <article className="condition-card">
          <div className="summary-panel-header">
            <h3>Current Conditions</h3>
            <span>Key inputs</span>
          </div>
          <div className="condition-list">
            <span><strong>{weatherAvailable ? `${highestRiskRegion.temperature}°C` : "--"}</strong>Temperature</span>
            <span><strong>{weatherAvailable ? `${highestRiskRegion.humidity}%` : "--"}</strong>Humidity</span>
            <span><strong>{weatherAvailable ? highestRiskRegion.windSpeed : "--"}</strong>km/h wind</span>
            <span><strong>{avgNdvi ?? "--"}</strong>Average NDVI</span>
          </div>
          <p><Leaf size={15} /> {highestRiskRegion.vegetationSource?.message ?? "Vegetation source unavailable."}</p>
          <p><Wind size={15} /> {highestRiskRegion.hotspotSource?.message ?? "Hotspot source unavailable."}</p>
        </article>
      </div>

      <footer className="prediction-summary-footer">
        <p>Priority action: {priorityAction}</p>
        <div>
          <Link className="button secondary" to="/prediction">View Detailed Prediction</Link>
          <Link className="button primary" to="/alerts">Review Alerts</Link>
        </div>
      </footer>
    </motion.section>
  );
}
