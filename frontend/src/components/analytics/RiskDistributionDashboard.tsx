import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  Download,
  Expand,
  Flame,
  Gauge,
  Leaf,
  MapPin,
  RefreshCcw,
  ShieldCheck,
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
import { RiskMap } from "../dashboard/RiskMap";
import { FeatureContribution, RegionRisk, TrendPoint, WeatherSnapshot } from "../../types";
import { useEnvironmentalContext } from "../../contexts/EnvironmentalContext";
import { ENVIRONMENTAL_QUERY_KEY } from "../../hooks/useEnvironmentalData";
import { buildRegionsCsv, downloadTextFile } from "../../utils/downloads";

interface RiskDistributionDashboardProps {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherData: WeatherSnapshot[];
}

function nbrLabel(region: RegionRisk) {
  if (region.riskStatus === "unavailable") return "Unavailable";
  return region.prediction?.defaulted_features?.includes("nbr") ? `Defaulted ${region.nbr}` : region.nbr;
}

const classificationPalette = {
  Safe: "#00a86b",
  Low: "#2e7d32",
  Moderate: "#fdd835",
  High: "#fb8c00",
  "Very High": "#e53935",
  Extreme: "#7f1d1d"
};

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function hasPrediction(region: RegionRisk) {
  return region.riskStatus !== "unavailable";
}

function hasProviderData(status?: string) {
  return status === "live" || status === "degraded";
}

function sourceStatus(source?: RegionRisk["riskSource"]) {
  return source?.dataStatus ?? (source?.status === "live" ? "LIVE" : "UNAVAILABLE");
}

function weatherText(region: RegionRisk, key: "temperature" | "humidity" | "windSpeed") {
  if (!hasProviderData(region.weatherSource?.status)) return "Unavailable";
  if (key === "temperature") return `${region.temperature}°C`;
  if (key === "humidity") return `${region.humidity}% humidity`;
  return `${region.windSpeed} km/h wind`;
}

function contributionColor(feature: FeatureContribution) {
  const groupColors: Record<FeatureContribution["influence_group"], string> = {
    weather: "#e53935",
    vegetation: "#2e7d32",
    historical: "#7f1d1d",
    model: "#1976d2"
  };
  return groupColors[feature.influence_group] ?? "#64748b";
}

function predictionTimestamp(region: RegionRisk) {
  const snapshotTimestamp = region.prediction?.input_snapshot?.snapshot_timestamp;
  if (typeof snapshotTimestamp === "string") return snapshotTimestamp;
  return region.riskSource?.retrievedAt;
}

function classifyRisk(score: number) {
  if (score >= 90) return "Extreme";
  if (score >= 80) return "Very High";
  if (score >= 60) return "High";
  if (score >= 40) return "Moderate";
  if (score >= 20) return "Low";
  return "Safe";
}

function matrixPosition(region: RegionRisk) {
  const likelihood = Math.min(5, Math.max(1, Math.ceil((hasPrediction(region) ? region.riskScore : 0) / 20)));
  const weatherPressure = hasProviderData(region.weatherSource?.status) ? region.windSpeed + region.temperature : 0;
  const hotspotPressure = hasProviderData(region.hotspotSource?.status) ? region.hotspots * 3 : 0;
  const impact = Math.min(5, Math.max(1, Math.ceil((hotspotPressure + weatherPressure) / 20)));
  return { likelihood, impact };
}

export function RiskDistributionDashboard({ regions, trendData, weatherData }: RiskDistributionDashboardProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { setSelectedRegionId } = useEnvironmentalContext();
  const predictedRegions = regions.filter(hasPrediction);
  const rankedRegions = [...regions].sort((a, b) => (hasPrediction(b) ? b.riskScore : -1) - (hasPrediction(a) ? a.riskScore : -1));
  const overallRisk = predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.riskScore))) : 0;
  const averageConfidence = predictedRegions.length ? Math.round(average(predictedRegions.map((region) => region.confidence))) : 0;
  const averageFwi = weatherData.length ? Math.round(average(weatherData.map((item) => item.fireWeatherIndex))) : null;
  const vegetationRegions = regions.filter((region) => hasProviderData(region.vegetationSource?.status));
  const vegetationHealth = vegetationRegions.length ? Math.round(average(vegetationRegions.map((region) => region.ndvi)) * 100) : null;
  const highRiskRegions = predictedRegions.filter((region) => region.riskScore >= 60).length;
  const criticalRegions = predictedRegions.filter((region) => region.riskScore >= 80).length;
  const latestPredictionAt = rankedRegions.map(predictionTimestamp).find(Boolean);
  const latestPredictionLabel = latestPredictionAt ? new Date(latestPredictionAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Unavailable";

  const contributorMap = new Map<string, { name: string; total: number; count: number; color: string }>();
  regions
    .filter((region) => region.prediction?.data_mode === "live")
    .flatMap((region) => region.prediction?.top_contributing_features ?? [])
    .forEach((feature) => {
      const key = feature.display_name;
      const existing = contributorMap.get(key);
      const value = Math.max(0, feature.importance * 100);
      contributorMap.set(key, {
        name: key,
        total: (existing?.total ?? 0) + value,
        count: (existing?.count ?? 0) + 1,
        color: existing?.color ?? contributionColor(feature)
      });
    });
  const contributorData = [...contributorMap.values()]
    .map((item) => ({ name: item.name, value: Math.round(item.total / item.count), color: item.color }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 7);
  const contributorTotal = contributorData.reduce((sum, item) => sum + item.value, 0);

  const probabilityHistogram = [
    { bucket: "0-20", min: 0, max: 20 },
    { bucket: "20-40", min: 20, max: 40 },
    { bucket: "40-60", min: 40, max: 60 },
    { bucket: "60-80", min: 60, max: 80 },
    { bucket: "80-100", min: 80, max: 101 }
  ].map((bucket) => {
    const count = predictedRegions.filter((region) => region.riskScore >= bucket.min && region.riskScore < bucket.max).length;
    return {
      bucket: bucket.bucket,
      regions: count,
      share: predictedRegions.length ? Math.round((count / predictedRegions.length) * 100) : 0
    };
  });

  const distribution = ["Safe", "Low", "Moderate", "High", "Very High", "Extreme"].map((label) => ({
    name: label,
    count: predictedRegions.filter((region) => classifyRisk(region.riskScore) === label).length,
    color: classificationPalette[label as keyof typeof classificationPalette]
  }));

  const gaugeStyle = {
    "--risk-gauge": `${overallRisk * 3.6}deg`
  } as CSSProperties & Record<"--risk-gauge", string>;

  const stats = [
    { label: "Overall Risk Score", value: predictedRegions.length ? `${overallRisk}` : "Unavailable", detail: `${predictedRegions.length} backend predictions`, icon: Gauge, tone: predictedRegions.length ? "danger" : "warning" },
    { label: "Avg Confidence", value: predictedRegions.length ? `${averageConfidence}%` : "Unavailable", detail: "backend prediction output", icon: ShieldCheck, tone: predictedRegions.length ? "success" : "warning" },
    { label: "Total Regions", value: `${regions.length}`, detail: "monitored divisions", icon: MapPin, tone: "neutral" },
    { label: "High Risk Regions", value: `${highRiskRegions}`, detail: "prioritize first", icon: AlertTriangle, tone: "warning" },
    { label: "Critical Regions", value: `${criticalRegions}`, detail: "immediate attention", icon: Flame, tone: "danger" },
    { label: "Avg Fire Weather", value: averageFwi === null ? "Unavailable" : `${averageFwi}`, detail: "Open-Meteo forecast", icon: Wind, tone: averageFwi === null ? "neutral" : "warning" },
    { label: "Vegetation Health", value: vegetationHealth === null ? "Unavailable" : `${vegetationHealth}%`, detail: "available NDVI scenes", icon: Leaf, tone: vegetationHealth === null ? "neutral" : "warning" },
    { label: "Last Prediction", value: latestPredictionLabel, detail: "latest backend snapshot", icon: CalendarDays, tone: "neutral" }
  ];
  const exportSnapshot = () => {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadTextFile(`firesight-risk-snapshot-${stamp}.csv`, buildRegionsCsv(regions, weatherData), "text/csv;charset=utf-8");
  };
  const requestFullscreen = () => {
    void document.querySelector(".risk-distribution")?.requestFullscreen?.();
  };
  const openRegionAnalysis = (regionId: string) => {
    setSelectedRegionId(regionId);
    navigate("/prediction");
  };
  const recommendations = rankedRegions.slice(0, 5).map((region) => {
    if (region.riskStatus === "unavailable") return `Review provider status for ${region.name} before operational action.`;
    if (region.hotspotSource?.status === "live" && region.hotspots > 0) {
      return `Verify ${region.hotspots} active hotspot${region.hotspots === 1 ? "" : "s"} in ${region.name}.`;
    }
    return `Continue weather and vegetation monitoring for ${region.name}.`;
  });

  return (
    <motion.section
      className="risk-distribution"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      aria-labelledby="risk-distribution-title"
    >
      <header className="risk-distribution-header">
        <div>
          <span className="eyebrow">Risk Distribution Dashboard</span>
          <h2 id="risk-distribution-title">
            <Flame size={28} /> Real-time AI Risk Classification
          </h2>
          <p>Visual command center for wildfire risk distribution, hotspot density, confidence, and region prioritization.</p>
        </div>
        <div className="risk-toolbar">
          <button className="button secondary" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY })}><RefreshCcw size={16} /> Refresh</button>
          <button className="button secondary" type="button" onClick={requestFullscreen}><Expand size={16} /> Fullscreen</button>
          <button className="button primary" type="button" onClick={exportSnapshot}><Download size={16} /> Export Snapshot</button>
        </div>
      </header>

      <div className="risk-stat-grid">
        {stats.map((stat) => (
          <article className={`risk-stat-card ${stat.tone}`} key={stat.label}>
            <stat.icon size={20} />
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
            <small>{stat.detail}</small>
          </article>
        ))}
      </div>

      <div className="risk-distribution-grid">
        <section className="risk-distribution-panel map-panel">
          <div className="risk-panel-header">
            <div>
              <h3>Interactive GIS Risk Heatmap</h3>
              <span>Risk zones, hotspots, weather overlay, and monitored forest regions</span>
            </div>
          </div>
          <RiskMap regions={regions} />
          <div className="map-legend">
            {Object.entries(classificationPalette).map(([label, color]) => (
              <span key={label}><i style={{ background: color }} /> {label}</span>
            ))}
          </div>
        </section>

        <section className="risk-distribution-panel gauge-panel">
          <div className="risk-panel-header">
            <h3>Overall Risk Gauge</h3>
            <span>0 safe · 100 extreme</span>
          </div>
          <div className="distribution-gauge" style={gaugeStyle}>
            <div>
              <strong>{overallRisk}</strong>
              <span>{classifyRisk(overallRisk)}</span>
            </div>
          </div>
          <p>{predictedRegions.length ? `${highRiskRegions} of ${predictedRegions.length} regions are currently high risk or above based on backend prediction output.` : "Backend predictions are unavailable, so no live risk gauge is shown."}</p>
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Risk Distribution</h3>
            <span>Category totals by current risk score</span>
          </div>
          <ResponsiveContainer width="100%" height={230}>
            <PieChart>
              <Pie data={distribution} dataKey="count" nameKey="name" innerRadius={58} outerRadius={88} paddingAngle={3}>
                {distribution.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="distribution-legend">
            {distribution.map((item) => (
              <span key={item.name}><i style={{ background: item.color }} /> {item.name}: {item.count}</span>
            ))}
          </div>
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Risk Score Buckets</h3>
            <span>Region share by current backend risk score</span>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={probabilityHistogram} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="bucket" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip />
              <Bar dataKey="share" fill="#fb8c00" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="confidence-strip">
            <span>Average {predictedRegions.length ? `${overallRisk}` : "Unavailable"}</span>
            <span>{predictedRegions.length} predicted regions</span>
            <span>{highRiskRegions} high risk or above</span>
          </div>
        </section>

        <section className="risk-distribution-panel wide">
          <div className="risk-panel-header">
            <h3>Regional Risk Cards</h3>
            <span>Synchronized drill-down targets</span>
          </div>
          <div className="regional-risk-grid">
            {rankedRegions.map((region) => (
              <article className="regional-risk-card" key={region.id}>
                <div className="region-card-top">
                  <div>
                    <strong>{region.name}</strong>
                    <span>{region.state}</span>
                  </div>
                  <b>{hasPrediction(region) ? classifyRisk(region.riskScore) : "Unavailable"}</b>
                </div>
                <div className="region-score-row">
                  <strong>{hasPrediction(region) ? region.riskScore : "--"}</strong>
                  <div>
                    <span style={{ width: `${hasPrediction(region) ? region.riskScore : 0}%` }} />
                  </div>
                </div>
                <div className="region-card-metrics">
                  <span>{hasPrediction(region) ? `${region.confidence}% confidence` : "Prediction unavailable"}</span>
                  <span>{hasProviderData(region.vegetationSource?.status) ? `NDVI ${region.ndvi}` : "NDVI unavailable"}</span>
                  <span>{weatherText(region, "temperature")}</span>
                  <span>{weatherText(region, "humidity")}</span>
                  <span>{weatherText(region, "windSpeed")}</span>
                  <span>{hasProviderData(region.hotspotSource?.status) ? `${region.hotspots} hotspots` : "Hotspots unavailable"}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Top High-Risk Regions</h3>
            <span>Prediction drill-down</span>
          </div>
          <div className="top-risk-list">
            {rankedRegions.map((region, index) => (
              <article key={region.id}>
                <b>{index + 1}</b>
                <div className="mini-map-tile"><MapPin size={16} /></div>
                <div>
                  <strong>{region.name}</strong>
                  <span>{hasPrediction(region) ? `${region.riskScore} risk · ${region.confidence}% confidence` : "Prediction unavailable"}</span>
                  <small>Prediction source: {sourceStatus(region.riskSource)}</small>
                </div>
                <button type="button" onClick={() => openRegionAnalysis(region.id)}>Open Analysis</button>
              </article>
            ))}
          </div>
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Risk Matrix</h3>
            <span>Likelihood x impact</span>
          </div>
          <div className="risk-matrix" aria-label="Risk likelihood impact matrix">
            {Array.from({ length: 25 }).map((_, index) => {
              const x = (index % 5) + 1;
              const y = 5 - Math.floor(index / 5);
              const cellRegions = regions.filter((region) => {
                const position = matrixPosition(region);
                return position.likelihood === x && position.impact === y;
              });
              const intensity = x + y;
              return (
                <div className={`matrix-cell level-${Math.min(5, Math.ceil(intensity / 2))}`} key={`${x}-${y}`}>
                  {cellRegions.map((region) => (
                    <span title={`${region.name}: ${hasPrediction(region) ? region.riskScore : "Unavailable"}`} key={region.id}>{region.name.slice(0, 2)}</span>
                  ))}
                </div>
              );
            })}
          </div>
          <div className="matrix-axis"><span>Impact</span><span>Likelihood</span></div>
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Feature Contribution</h3>
            <span>Backend feature importance</span>
          </div>
          {contributorData.length ? (
            <>
              <div className="stacked-contribution">
                {contributorData.map((item) => (
                  <span key={item.name} style={{ width: `${Math.round((item.value / contributorTotal) * 100)}%`, background: item.color }} title={`${item.name}: ${item.value}%`} />
                ))}
              </div>
              <div className="contributor-list">
                {contributorData.map((item) => (
                  <article key={item.name}>
                    <i style={{ background: item.color }} />
                    <span>{item.name}</span>
                    <strong>{item.value}%</strong>
                  </article>
                ))}
              </div>
            </>
          ) : <p>No live backend feature contribution data is available.</p>}
        </section>

        <section className="risk-distribution-panel">
          <div className="risk-panel-header">
            <h3>Risk Evolution</h3>
            <span>Development trend fixture, not live history</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={trendData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
              <defs>
                <linearGradient id="distributionRiskGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#e53935" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#e53935" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip />
              <Area type="monotone" dataKey="risk" stroke="#e53935" fill="url(#distributionRiskGradient)" strokeWidth={3} />
            </AreaChart>
          </ResponsiveContainer>
        </section>

        <section className="risk-distribution-panel wide">
          <div className="risk-panel-header">
            <h3>Regional Comparison Table</h3>
            <span>Regional values included in CSV exports</span>
          </div>
          <div className="risk-comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Risk</th>
                  <th>Confidence</th>
                  <th>Temperature</th>
                  <th>Humidity</th>
                  <th>NDVI</th>
                  <th>NBR</th>
                  <th>FWI</th>
                  <th>Prediction Source</th>
                </tr>
              </thead>
              <tbody>
                {rankedRegions.map((region) => (
                  <tr key={region.id}>
                    <td><strong>{region.name}</strong><span>{region.state}</span></td>
                    <td>{hasPrediction(region) ? region.riskScore : "Unavailable"}</td>
                    <td>{hasPrediction(region) ? `${region.confidence}%` : "Unavailable"}</td>
                    <td>{hasProviderData(region.weatherSource?.status) ? `${region.temperature}°C` : "Unavailable"}</td>
                    <td>{hasProviderData(region.weatherSource?.status) ? `${region.humidity}%` : "Unavailable"}</td>
                    <td>{hasProviderData(region.vegetationSource?.status) ? region.ndvi : "Unavailable"}</td>
                    <td>{nbrLabel(region)}</td>
                    <td>{averageFwi ?? "Unavailable"}</td>
                    <td>{sourceStatus(region.riskSource)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="risk-distribution-panel recommendations-panel">
          <div className="risk-panel-header">
            <h3>AI Recommendations</h3>
            <Activity size={18} />
          </div>
          {recommendations.map((recommendation, index) => (
            <article key={recommendation}>
              <b>Priority {index + 1}</b>
              <span>{recommendation}</span>
            </article>
          ))}
        </section>

        <section className="risk-distribution-panel explanation-panel">
          <div className="risk-panel-header">
            <h3>Executive Explanation</h3>
            <ThermometerSun size={18} />
          </div>
          <p>
            {predictedRegions.length
              ? `${highRiskRegions} monitored region${highRiskRegions === 1 ? "" : "s"} currently rank high risk or above. Use the region drill-downs for backend prediction details and provider status before deciding field action.`
              : "Live backend predictions are unavailable, so this view is limited to provider status and regional context."}
          </p>
        </section>
      </div>
    </motion.section>
  );
}
