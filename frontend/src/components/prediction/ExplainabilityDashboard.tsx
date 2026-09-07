import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BrainCircuit,
  CheckCircle2,
  CloudSun,
  Download,
  FlaskConical,
  Gauge,
  GitBranch,
  History,
  Leaf,
  LineChart as LineChartIcon,
  Radar,
  RefreshCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  ThermometerSun,
  Wind
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { RegionRisk, TrendPoint, WeatherSnapshot } from "../../types";
import { downloadTextFile, htmlEscape, safeFileNamePart } from "../../utils/downloads";
import { ENVIRONMENTAL_QUERY_KEY } from "../../hooks/useEnvironmentalData";

interface ExplainabilityDashboardProps {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherData: WeatherSnapshot[];
  selectedRegionId?: string;
}

const featureImportance = [
  { name: "Temperature", value: 36, impact: "positive", trend: "weather input", explanation: "Temperature contribution is recalculated from the current weather input when live weather is available." },
  { name: "Humidity", value: 24, impact: "positive", trend: "below 20%", explanation: "Very low humidity removes moisture protection from dry fuels." },
  { name: "Wind Speed", value: 18, impact: "positive", trend: "+11%", explanation: "Wind increases spread potential once ignition occurs." },
  { name: "Rainfall", value: 7, impact: "negative", trend: "limited relief", explanation: "Recent rainfall slightly reduces risk, but totals remain low." },
  { name: "NDVI", value: 13, impact: "positive", trend: "declining", explanation: "Vegetation health decline indicates more dry biomass." },
  { name: "NBR", value: 10, impact: "positive", trend: "stress rising", explanation: "Burn-ratio stress suggests vulnerable vegetation patches." },
  { name: "Fire Weather Risk Index", value: 31, impact: "positive", trend: "app metric", explanation: "This is an application-specific weather risk indicator, not the official Canadian FWI." },
  { name: "Historical Fire Density", value: 9, impact: "positive", trend: "fixture", explanation: "Historical density is currently a development fixture until validated records are connected." }
];

const probabilityData = [
  { name: "Low", value: 7, color: "#00a86b" },
  { name: "Moderate", value: 18, color: "#fdd835" },
  { name: "High", value: 52, color: "#fb8c00" },
  { name: "Very High", value: 17, color: "#e53935" },
  { name: "Extreme", value: 6, color: "#7f1d1d" }
];

const historicalEvents = [
  { event: "Fixture dry wind scenario", similarity: 94, risk: "High", outcome: "Example outcome", weather: "simulated weather" },
  { event: "Fixture buffer zone scenario", similarity: 88, risk: "High", outcome: "Example outcome", weather: "simulated weather" },
  { event: "Fixture heat stress scenario", similarity: 81, risk: "Moderate", outcome: "Example outcome", weather: "simulated weather" }
];

const reasoningSteps = [
  "Weather updated",
  "Satellite fixture checked",
  "Vegetation fixture loaded",
  "Features generated",
  "Random Forest prediction",
  "Confidence estimated",
  "Recommendation generated"
];

const recommendations = [
  { priority: "Critical", action: "Increase monitoring frequency in the highest-risk region.", impact: "High" },
  { priority: "High", action: "Deploy drone surveillance during the predicted ignition window.", impact: "High" },
  { priority: "High", action: "Restrict controlled burning until humidity recovers.", impact: "Medium" },
  { priority: "Medium", action: "Monitor satellite and weather updates every hour.", impact: "Medium" }
];

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function classifyRisk(score: number) {
  if (score >= 90) return "Extreme";
  if (score >= 80) return "Very High";
  if (score >= 60) return "High";
  if (score >= 40) return "Moderate";
  return "Low";
}

function formatValue(value: unknown, fallback = "Unavailable") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

export function buildExplainabilityReport(region: RegionRisk, weather: WeatherSnapshot | undefined, generatedAt: Date, timeline: string[]) {
  const prediction = region.prediction;
  if (!prediction || prediction.status !== "ok") {
    throw new Error("A live backend prediction is required before explainability can be exported.");
  }
  const features = prediction.feature_values ?? {};
  const dataQuality = prediction.data_quality ?? {};
  const provenance = prediction.data_provenance ?? {};
  const rows: Array<[string, unknown]> = [
    ["Risk score", prediction.risk_score],
    ["Risk category", prediction.risk_level],
    ["Confidence", typeof prediction.confidence === "number" ? `${prediction.confidence}%` : undefined],
    ["Model version", prediction.model_version],
    ["Data mode", prediction.data_mode]
  ];
  const featureRows: Array<[string, unknown]> = [
    ["Temperature", features.temperature ?? weather?.temperature],
    ["Humidity", features.humidity ?? weather?.humidity],
    ["Wind speed", features.wind_speed ?? weather?.wind],
    ["Rainfall", features.rainfall ?? weather?.rainfall],
    ["NDVI", features.ndvi ?? region.ndvi],
    ["NBR", features.nbr ?? region.nbr],
    ["Hotspots", features.hotspots ?? region.hotspots],
    ["Fire weather index", features.fire_weather_index ?? weather?.fireWeatherIndex]
  ];
  const qualityRows: Array<[string, unknown]> = [
    ["Weather status", region.weatherSource?.dataStatus ?? dataQuality.weather],
    ["Weather provider", region.weatherSource?.provider],
    ["Vegetation status", region.vegetationSource?.dataStatus ?? dataQuality.vegetation],
    ["Vegetation provider", region.vegetationSource?.provider],
    ["Hotspot status", region.hotspotSource?.dataStatus ?? dataQuality.hotspots],
    ["Hotspot provider", region.hotspotSource?.provider],
    ["Risk source", region.riskSource?.provider],
    ["Defaulted features", prediction.defaulted_features?.join(", ") || "None"]
  ];
  const renderRows = (items: Array<[string, unknown]>) => items.map(([label, value]) => `<tr><th>${htmlEscape(label)}</th><td>${htmlEscape(formatValue(value))}</td></tr>`).join("");
  const renderList = (items: string[] | undefined, empty: string) => (items?.length ? items : [empty]).map((item) => `<li>${htmlEscape(item)}</li>`).join("");
  const renderContributions = () => (prediction.top_contributing_features?.length
    ? prediction.top_contributing_features.map((feature) => `<li><strong>${htmlEscape(feature.display_name)}</strong>: ${htmlEscape(feature.explanation)} <span>(${htmlEscape(feature.direction)}, value ${htmlEscape(feature.value)})</span></li>`).join("")
    : "<li>No backend feature contribution details were returned.</li>");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FireSight AI Explainability Report - ${htmlEscape(region.name)}</title>
  <style>
    body { font-family: Inter, Arial, sans-serif; color: #17202a; margin: 32px; line-height: 1.5; }
    h1, h2 { margin: 0 0 10px; }
    h1 { color: #123524; letter-spacing: 0.04em; text-transform: uppercase; }
    section { margin-top: 24px; page-break-inside: avoid; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #d8e2dc; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { width: 220px; background: #eff7f1; }
    li { margin: 6px 0; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f6f8f7; border: 1px solid #d8e2dc; padding: 12px; }
    .summary { background: #f1f8f4; border: 1px solid #c7dfcf; padding: 14px; }
  </style>
</head>
<body>
  <h1>FireSight AI</h1>
  <h2>Explainability Report</h2>
  <div class="summary">
    <strong>Region:</strong> ${htmlEscape(region.name)}<br />
    <strong>Generated at:</strong> ${htmlEscape(generatedAt.toLocaleString())}<br />
    <strong>Explanation:</strong> ${htmlEscape(prediction.explanation ?? "No backend explanation summary was returned.")}
  </div>
  <section>
    <h2>Prediction</h2>
    <table><tbody>${renderRows(rows)}</tbody></table>
  </section>
  <section>
    <h2>Environmental Features</h2>
    <table><tbody>${renderRows(featureRows)}</tbody></table>
  </section>
  <section>
    <h2>Data Quality</h2>
    <table><tbody>${renderRows(qualityRows)}</tbody></table>
  </section>
  <section>
    <h2>Risk Increasing Factors</h2>
    <ul>${renderList(prediction.risk_factors, "No backend risk-increasing factors were returned.")}</ul>
  </section>
  <section>
    <h2>Risk Reducing Factors</h2>
    <ul>${renderList(prediction.weather_influence, "No backend risk-reducing factors were returned.")}</ul>
  </section>
  <section>
    <h2>Feature Contributions</h2>
    <ul>${renderContributions()}</ul>
  </section>
  <section>
    <h2>AI Reasoning Timeline</h2>
    <ol>${timeline.map((step) => `<li>${htmlEscape(step)}</li>`).join("")}</ol>
  </section>
  <section>
    <h2>Data Provenance</h2>
    <pre>${htmlEscape(JSON.stringify(provenance, null, 2))}</pre>
  </section>
</body>
</html>`;
}

export function ExplainabilityDashboard({ regions, trendData, weatherData, selectedRegionId }: ExplainabilityDashboardProps) {
  const queryClient = useQueryClient();
  const [exportState, setExportState] = useState<"idle" | "preparing">("idle");
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const latestWeather = weatherData[0];
  const selectedRegion = regions.find((region) => region.id === selectedRegionId) ?? regions[0];
  const predictionResponse = selectedRegion.prediction?.status === "ok" ? selectedRegion.prediction : undefined;
  const livePrediction = predictionResponse?.data_mode === "live" ? predictionResponse : undefined;
  const predictionUnavailable = selectedRegion.riskStatus === "unavailable";
  const simulationMode = selectedRegion.riskStatus === "simulation";

  const predictedRegions = regions.filter((region) => region.riskStatus !== "unavailable");
  const confidence = livePrediction?.confidence ?? predictionResponse?.confidence ?? (predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.confidence))) : 0);
  const baseRisk = livePrediction?.risk_score ?? predictionResponse?.risk_score ?? (predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.riskScore))) : 0);
  const displayedFeatureImportance = livePrediction?.top_contributing_features?.length
    ? livePrediction.top_contributing_features.map((feature) => ({
        name: feature.display_name,
        value: Math.round(feature.importance * 100),
        impact: feature.direction === "reduces_risk" ? "negative" : "positive",
        trend: `value ${feature.value}`,
        explanation: feature.explanation
      }))
    : predictionUnavailable
      ? []
      : featureImportance;
  const comparisonData = [
    { label: "Today", risk: baseRisk, confidence, weather: latestWeather?.provider ?? "weather source", vegetation: livePrediction ? "Live" : simulationMode ? "Simulation" : "Unavailable", className: livePrediction?.risk_level ?? classifyRisk(baseRisk) },
    { label: "Yesterday", risk: 74, confidence: 91, weather: "Fixture", vegetation: "Fixture", className: "High" },
    { label: "Last Week", risk: 58, confidence: 86, weather: "Fixture", vegetation: "Fixture", className: "Moderate" },
    { label: "Last Month", risk: 41, confidence: 82, weather: "Fixture", vegetation: "Fixture", className: "Moderate" },
    { label: "Historical Avg", risk: 49, confidence: 79, weather: "Fixture", vegetation: "Fixture", className: "Moderate" }
  ].filter((item) => simulationMode || item.label === "Today");
  const contributorIncreases = livePrediction?.risk_factors?.length ? livePrediction.risk_factors : predictionUnavailable ? ["Live prediction unavailable"] : ["Weather input", "Strong wind", "Low humidity", "Vegetation fixture"];
  const contributorReductions = livePrediction ? livePrediction.weather_influence ?? [] : predictionUnavailable ? ["No backend contribution data"] : ["Recent rainfall", "Healthy NDVI pockets", "Night cooling", "Lower wind zones"];
  const reasoningTimeline = livePrediction
    ? ["Environmental snapshot loaded", "Existing ML features mapped", "FireRiskModelService prediction", "Backend explanation returned"]
    : predictionUnavailable
      ? selectedRegion.prediction?.missing_sources?.map((item) => `${item.source}: ${item.status}`) ?? ["Prediction unavailable"]
      : reasoningSteps;

  const exportExplainability = () => {
    setExportMessage(null);
    if (!livePrediction) {
      setExportMessage("A live backend prediction is required before explainability can be exported.");
      return;
    }
    if (exportState === "preparing") {
      return;
    }
    setExportState("preparing");
    try {
      const generatedAt = new Date();
      const report = buildExplainabilityReport(selectedRegion, latestWeather, generatedAt, reasoningTimeline);
      const stamp = generatedAt.toISOString().slice(0, 19).replace(/[:T]/g, "-");
      downloadTextFile(`firesight-explainability-${safeFileNamePart(selectedRegion.name)}-${stamp}.html`, report, "text/html;charset=utf-8");
    } catch (error) {
      setExportMessage(error instanceof Error ? error.message : "Explainability export failed.");
    } finally {
      window.setTimeout(() => setExportState("idle"), 250);
    }
  };

  const featureValues = livePrediction?.feature_values;
  const decisionNodes = [
    { rule: "Temperature", value: typeof featureValues?.temperature === "number" ? `${featureValues.temperature}°C` : "Unavailable", active: Boolean(livePrediction) },
    { rule: "Humidity", value: typeof featureValues?.humidity === "number" ? `${featureValues.humidity}%` : "Unavailable", active: Boolean(livePrediction) },
    { rule: "NDVI", value: typeof featureValues?.ndvi === "number" ? featureValues.ndvi.toFixed(2) : "Unavailable", active: Boolean(livePrediction) },
    { rule: "Wind Speed", value: typeof featureValues?.wind_speed === "number" ? `${featureValues.wind_speed} km/h` : "Unavailable", active: Boolean(livePrediction) },
    { rule: "Backend prediction", value: livePrediction?.risk_level ?? "Unavailable", active: Boolean(livePrediction) }
  ];

  const shapData = [
    { name: "Baseline", value: 42, fill: "#64748b" },
    { name: "Temperature", value: 18, fill: "#e53935" },
    { name: "Humidity", value: 13, fill: "#fb8c00" },
    { name: "Wind", value: 8, fill: "#f59e0b" },
    { name: "NDVI", value: 6, fill: "#2e7d32" },
    { name: "Rainfall", value: -4, fill: "#1976d2" }
  ];
  const contributionBars = livePrediction?.visual_explanations?.contribution_bars as Array<{ feature: string; contribution: number; direction: string }> | undefined;
  const shapChartData = contributionBars?.map((item) => ({
    name: item.feature,
    value: item.contribution,
    fill: item.direction === "reduces_risk" ? "#1976d2" : "#e53935"
  })) ?? (predictionUnavailable ? [] : shapData);
  const performanceRows = livePrediction
    ? [["Model Version", livePrediction.model_version ?? "Unavailable"], ["Confidence", `${livePrediction.confidence}%`], ["Risk Score", `${livePrediction.risk_score}/100`], ["Risk Class", livePrediction.risk_level]]
    : simulationMode
      ? [["Accuracy", "91.2%"], ["Precision", "89.4%"], ["Recall", "87.9%"], ["F1 Score", "88.6%"]]
      : [["Model Version", "Unavailable"], ["Confidence", "Unavailable"], ["Risk Score", "Unavailable"], ["Risk Class", "Unavailable"]];
  const uncertaintyRows = livePrediction
    ? [
        ["Weather status", selectedRegion.weatherSource?.dataStatus ?? "UNAVAILABLE"],
        ["Vegetation status", selectedRegion.vegetationSource?.dataStatus ?? "UNAVAILABLE"],
        ["Hotspot status", selectedRegion.hotspotSource?.dataStatus ?? "UNAVAILABLE"],
        ["Confidence", `${livePrediction.confidence}%`]
      ]
    : simulationMode
      ? [["Missing data", "4%"], ["Cloud cover impact", "8%"], ["Weather quality risk", "6%"], ["Satellite age", "9%"]]
      : [["Weather status", selectedRegion.weatherSource?.dataStatus ?? "UNAVAILABLE"], ["Vegetation status", selectedRegion.vegetationSource?.dataStatus ?? "UNAVAILABLE"], ["Hotspot status", selectedRegion.hotspotSource?.dataStatus ?? "UNAVAILABLE"], ["Prediction", "Unavailable"]];
  const recommendationRows = livePrediction?.recommendations?.length
    ? livePrediction.recommendations
    : simulationMode
      ? recommendations.map((item) => item.action)
      : ["No backend recommendations are available until a live prediction is generated."];

  return (
    <motion.section
      className="xai-dashboard"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      aria-labelledby="xai-dashboard-title"
    >
      <header className="xai-hero">
        <div>
          <span className="eyebrow">Prediction Comparison & Explainability</span>
          <h2 id="xai-dashboard-title"><BrainCircuit size={30} /> AI Explanation</h2>
          <p>{livePrediction?.explanation ?? selectedRegion.riskSource?.message ?? "Live prediction unavailable. No fixture explanation is shown for the selected region."}</p>
        </div>
        <div className="xai-executive-panel">
          <span>Risk <strong>{livePrediction?.risk_level ?? "Unavailable"}</strong></span>
          <span>Confidence <strong>{livePrediction?.confidence ? `${livePrediction.confidence}%` : "Unavailable"}</strong></span>
          <span>Source <strong>{selectedRegion.riskSource?.status ?? "unavailable"}</strong></span>
          <span>Updated <strong>{selectedRegion.riskSource?.dataStatus ?? "UNAVAILABLE"}</strong></span>
        </div>
      </header>

      <div className="xai-grid">
        <section className="xai-panel wide">
          <div className="xai-panel-header">
            <h3><Gauge size={18} /> Feature Importance</h3>
            <button className="button secondary" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY })}><RefreshCcw size={15} /> Recompute</button>
          </div>
          <div className="feature-importance-list">
            {displayedFeatureImportance.length === 0 ? (
              <article className="unavailable-row">
                <div>
                  <strong>Live prediction unavailable</strong>
                  <span>{selectedRegion.riskSource?.message ?? "Required live environmental inputs are unavailable."}</span>
                </div>
              </article>
            ) : displayedFeatureImportance.map((feature) => (
              <article key={feature.name}>
                <div>
                  <strong>{feature.name}</strong>
                  <span>{feature.explanation}</span>
                </div>
                <div className="feature-bar">
                  <span className={feature.impact} style={{ width: `${feature.value}%` }} />
                </div>
                <b>{feature.value}%</b>
                <em>{feature.impact === "positive" ? <ArrowUp size={14} /> : <ArrowDown size={14} />} {feature.trend}</em>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><ShieldCheck size={18} /> Model Confidence</h3>
            <span>{livePrediction ? "Backend confidence" : simulationMode ? "Simulation fixture" : "Unavailable"}</span>
          </div>
          <div
            className="xai-confidence-gauge"
            style={{ "--xai-confidence": `${confidence * 3.6}deg` } as CSSProperties & Record<"--xai-confidence", string>}
          >
            <div><strong>{confidence}%</strong><span>confidence</span></div>
          </div>
          <p>{livePrediction?.confidence_explanation ?? "Confidence is unavailable because the backend did not produce a live prediction."}</p>
          <div className="xai-mini-badges">
            <span>{selectedRegion.weatherSource?.dataStatus ?? "Weather unavailable"}</span>
            <span>{selectedRegion.vegetationSource?.dataStatus ?? "NDVI unavailable"}</span>
            <span>{selectedRegion.hotspotSource?.dataStatus ?? "FIRMS unavailable"}</span>
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><GitBranch size={18} /> Decision Path</h3>
            <span>Current values</span>
          </div>
          <div className="decision-path">
            {decisionNodes.map((node, index) => (
              <article className={node.active ? "active" : ""} key={node.rule}>
                <b>{index + 1}</b>
                <div><strong>{node.rule}</strong><span>{node.value}</span></div>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel split">
          <div>
            <div className="xai-panel-header">
              <h3><ArrowUp size={18} /> Risk Increasing</h3>
            </div>
            <div className="contributor-stack">
              {contributorIncreases.map((item) => (
                <span className="risk-up" key={item}>{item}</span>
              ))}
            </div>
          </div>
          <div>
            <div className="xai-panel-header">
              <h3><ArrowDown size={18} /> Risk Reducing</h3>
            </div>
            <div className="contributor-stack">
              {contributorReductions.map((item) => (
                <span className="risk-down" key={item}>{item}</span>
              ))}
            </div>
          </div>
        </section>

        <section className="xai-panel wide">
          <div className="xai-panel-header">
            <h3><SlidersHorizontal size={18} /> Feature Snapshot</h3>
            <span>Backend-owned prediction</span>
          </div>
          <div className="what-if-grid">
            {[
              ["Temperature", typeof featureValues?.temperature === "number" ? `${featureValues.temperature}°C` : "Unavailable"],
              ["Humidity", typeof featureValues?.humidity === "number" ? `${featureValues.humidity}%` : "Unavailable"],
              ["Wind Speed", typeof featureValues?.wind_speed === "number" ? `${featureValues.wind_speed} km/h` : "Unavailable"],
              ["Rainfall", typeof featureValues?.rainfall === "number" ? `${featureValues.rainfall} mm` : "Unavailable"],
              ["NDVI", typeof featureValues?.ndvi === "number" ? featureValues.ndvi.toFixed(2) : "Unavailable"],
              ["Hotspots", typeof featureValues?.hotspots === "number" ? `${featureValues.hotspots}` : "Unavailable"]
            ].map(([label, value]) => (
              <label key={label as string}>
                <span>{label as string} <strong>{value as string}</strong></span>
              </label>
            ))}
            <div className="what-if-output">
              <span>Current Prediction</span>
              <strong>{livePrediction?.risk_score ?? "--"}</strong>
              <b>{livePrediction?.risk_level ?? "Unavailable"}</b>
              <small>{livePrediction ? `Confidence ${livePrediction.confidence}%` : "No frontend risk calculation"}</small>
            </div>
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><FlaskConical size={18} /> Probability</h3>
            <span>Class distribution</span>
          </div>
          {livePrediction ? (
            <div className="xai-confidence-gauge" style={{ "--xai-confidence": `${confidence * 3.6}deg` } as CSSProperties & Record<"--xai-confidence", string>}>
              <div><strong>{confidence}%</strong><span>confidence</span></div>
            </div>
          ) : simulationMode ? (
            <ResponsiveContainer width="100%" height={230}>
              <PieChart>
                <Pie data={probabilityData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={86} paddingAngle={3}>
                  {probabilityData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p>Live class distribution is unavailable because the backend did not generate a current prediction.</p>
          )}
          <div className="xai-mini-badges">
            {livePrediction ? <span>{livePrediction.risk_level} · {livePrediction.confidence}% confidence</span> : <span>Live class distribution unavailable</span>}
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><History size={18} /> Similar Events</h3>
            <span>Historical match</span>
          </div>
          <div className="historical-events">
            {livePrediction ? (
              <article>
                <strong>Backend historical comparison</strong>
                <span>{String(livePrediction.historical_comparison?.comparison_text ?? "Comparison unavailable")}</span>
                <small>Existing explanation engine</small>
              </article>
            ) : predictionUnavailable ? (
              <article>
                <strong>Prediction unavailable</strong>
                <span>No live historical comparison returned.</span>
                <small>Waiting for required environmental inputs</small>
              </article>
            ) : historicalEvents.map((event) => (
              <article key={event.event}>
                <strong>{event.event}</strong>
                <span>{event.similarity}% similar · {event.risk}</span>
                <small>{event.weather} · {event.outcome}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><LineChartIcon size={18} /> Prediction Comparison</h3>
            <span>Today vs history</span>
          </div>
          <div className="comparison-cards">
            {comparisonData.map((item) => (
              <article key={item.label}>
                <strong>{item.label}</strong>
                <span>{livePrediction || selectedRegion.riskStatus === "simulation" ? `${item.risk} risk · ${item.confidence}% confidence` : "Prediction unavailable"}</span>
                <small>{item.weather} · {item.vegetation} · {item.className}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><Radar size={18} /> Performance</h3>
            <span>{livePrediction?.model_version ?? "Unavailable"}</span>
          </div>
          <div className="performance-grid">
            {performanceRows.map(([label, value]) => (
              <article key={label}><span>{label}</span><strong>{value}</strong></article>
            ))}
          </div>
        </section>

        <section className="xai-panel wide">
          <div className="xai-panel-header">
            <h3><CloudSun size={18} /> Contribution View</h3>
            <span>{livePrediction ? "Backend explanation" : "Unavailable"}</span>
          </div>
          {shapChartData.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={shapChartData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {shapChartData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p>No backend contribution data is available.</p>}
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><Leaf size={18} /> LIME-style Local Explanation</h3>
          </div>
          <p>{livePrediction?.explanation_details?.why ?? `Live local explanation is unavailable for ${selectedRegion.name}.`}</p>
          {livePrediction ? (
            <div className="xai-mini-badges">
              {(livePrediction.top_contributing_features ?? []).slice(0, 3).map((feature) => <span key={feature.feature}>{feature.display_name}: {feature.value}</span>)}
            </div>
          ) : null}
        </section>

        <section className="xai-panel">
          <div className="xai-panel-header">
            <h3><AlertTriangle size={18} /> Uncertainty</h3>
            <span>{livePrediction ? "Backend status" : "Unavailable"}</span>
          </div>
          <div className="uncertainty-list">
            {uncertaintyRows.map(([label, value]) => (
              <article key={label as string}>
                <span>{label as string}</span>
                <div><i style={{ width: livePrediction ? `${Math.min(100, confidence)}%` : simulationMode && String(value).endsWith("%") ? String(value) : "0%" }} /></div>
                <strong>{value as string}</strong>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel wide">
          <div className="xai-panel-header">
            <h3><Sparkles size={18} /> AI Reasoning Timeline</h3>
            <button className="button primary" type="button" disabled={exportState === "preparing"} onClick={exportExplainability}>
              <Download size={15} /> {exportState === "preparing" ? "Preparing Export..." : "Export Explainability"}
            </button>
          </div>
          {exportMessage ? <p className="export-feedback" role="alert">{exportMessage}</p> : null}
          <div className="reasoning-timeline">
            {reasoningTimeline.map((step, index) => (
              <article key={step}>
                <b>{index + 1}</b>
                <span>{step}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="xai-panel wide recommendations-panel">
          <div className="xai-panel-header">
            <h3><ThermometerSun size={18} /> Recommendation Engine</h3>
            <span>{livePrediction ? "Backend recommendations" : simulationMode ? "Simulation fixture" : "Unavailable"}</span>
          </div>
          {recommendationRows.map((recommendation, index) => (
            <article key={recommendation}>
              <b>Priority {index + 1}</b>
              <span>{recommendation}</span>
              <small>{livePrediction ? "backend recommendation" : simulationMode ? "fixture recommendation" : "unavailable"}</small>
            </article>
          ))}
        </section>
      </div>

      <footer className="xai-footer">
        <span><CheckCircle2 size={15} /> Prediction: {livePrediction ? "Available" : "Unavailable"}</span>
        <span><Wind size={15} /> Weather: {selectedRegion.weatherSource?.dataStatus ?? "UNAVAILABLE"}</span>
        <span><Leaf size={15} /> Satellite: {selectedRegion.vegetationSource?.dataStatus ?? "UNAVAILABLE"}</span>
        <span><ArrowRight size={15} /> Region: {selectedRegion.name}</span>
      </footer>
    </motion.section>
  );
}
