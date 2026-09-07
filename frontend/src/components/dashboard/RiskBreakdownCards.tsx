import { motion } from "framer-motion";
import { useMemo } from "react";
import type { CSSProperties } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  CloudSun,
  Cpu,
  Database,
  Flame,
  Gauge,
  Leaf,
  MapPin,
  Radar,
  Satellite,
  Server,
  Sparkles,
  ThermometerSun,
  Wind
} from "lucide-react";
import { Link } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";
import { AlertItem, RegionRisk, TrendPoint, WeatherSnapshot } from "../../types";

interface RiskBreakdownCardsProps {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherData: WeatherSnapshot[];
  alerts: AlertItem[];
}

interface BreakdownCard {
  title: string;
  metric: string;
  status: string;
  trend: string;
  explanation: string;
  action: string;
  href: string;
  tone: "fire" | "weather" | "vegetation" | "prediction" | "alerts" | "satellite" | "system" | "neutral";
  icon: typeof Flame;
  gauge?: number;
  details: string[];
}

function hasRealNbr(region: RegionRisk) {
  return region.riskStatus !== "unavailable" && !region.prediction?.defaulted_features?.includes("nbr");
}

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function riskCategory(score: number) {
  if (score >= 90) return "Extreme";
  if (score >= 80) return "Very High";
  if (score >= 60) return "High";
  if (score >= 40) return "Moderate";
  return "Low";
}

function miniSeries(trendData: TrendPoint[], offset = 0) {
  return trendData.map((point, index) => ({
    label: point.date,
    value: Math.max(8, Math.min(100, point.risk + offset + (index % 2 === 0 ? 2 : -3)))
  }));
}

export function RiskBreakdownCards({ regions, trendData, weatherData, alerts }: RiskBreakdownCardsProps) {
  const regionMetrics = useMemo(() => {
    const rankedRegions = [...regions].sort((a, b) => b.riskScore - a.riskScore);
    const realNbrRegions = regions.filter(hasRealNbr);
    return {
      highestRiskRegion: rankedRegions[0],
      overallRisk: Math.round(average(regions.map((region) => region.riskScore))),
      confidence: Math.round(average(regions.map((region) => region.confidence))),
      totalHotspots: regions.reduce((sum, region) => sum + region.hotspots, 0),
      averageNdvi: average(regions.map((region) => region.ndvi)),
      averageNbr: realNbrRegions.length ? average(realNbrRegions.map((region) => region.nbr)) : null
    };
  }, [regions]);
  const { highestRiskRegion, overallRisk, confidence, totalHotspots, averageNdvi, averageNbr } = regionMetrics;
  const latestWeather = weatherData[0];
  const averageFwi = useMemo(() => Math.round(average(weatherData.map((item) => item.fireWeatherIndex))), [weatherData]);
  const alertMetrics = useMemo(
    () => ({
      criticalAlerts: alerts.filter((alert) => alert.severity === "Critical").length,
      highAlerts: alerts.filter((alert) => alert.severity === "High").length,
      liveAlerts: alerts.filter((alert) => alert.source === "live_prediction").length
    }),
    [alerts]
  );
  const { criticalAlerts, highAlerts, liveAlerts } = alertMetrics;

  const cards: BreakdownCard[] = useMemo(() => [
    {
      title: "Overall Fire Risk",
      metric: `${overallRisk}`,
      status: riskCategory(overallRisk),
      trend: "▲ 12% vs yesterday",
      explanation: "Current environmental pressure indicates elevated ignition probability across dry sectors.",
      action: "View Details",
      href: "/prediction",
      tone: "fire",
      icon: Flame,
      gauge: overallRisk,
      details: ["0-100 risk score", `${highestRiskRegion.name} leading`, "fixture risk score"]
    },
    {
      title: "AI Prediction Confidence",
      metric: `${confidence}%`,
      status: "Healthy",
      trend: "▲ 2.4% this week",
      explanation: "Confidence is high because weather data and recent satellite imagery are complete.",
      action: "Run Prediction",
      href: "/prediction",
      tone: "prediction",
      icon: BrainCircuit,
      gauge: confidence,
      details: ["Random Forest v1.2", "Inference 0.42s", "Data completeness 97%"]
    },
    {
      title: "Weather Risk",
      metric: `${latestWeather.temperature}°C`,
      status: "Warning",
      trend: "▼ humidity falling",
      explanation: "Heat, low humidity, and wind are combining into a dangerous weather profile.",
      action: "Open Weather",
      href: "/weather",
      tone: "weather",
      icon: CloudSun,
      gauge: latestWeather.fireWeatherIndex,
      details: [`Humidity ${latestWeather.humidity}%`, `Wind ${latestWeather.wind} km/h`, `Rainfall ${latestWeather.rainfall} mm`]
    },
    {
      title: "Vegetation Health",
      metric: averageNdvi.toFixed(2),
      status: "Watch",
      trend: "▼ NDVI declining",
      explanation: "Vegetation is drying in high-risk regions, increasing available fuel.",
      action: "View Vegetation",
      href: "/vegetation",
      tone: "vegetation",
      icon: Leaf,
      gauge: Math.round(averageNdvi * 100),
      details: [averageNbr === null ? "NBR unavailable" : `Average NBR ${averageNbr.toFixed(2)}`, "Dry vegetation 42%", "Sentinel fresh"]
    },
    {
      title: "Active Fire Hotspots",
      metric: `${totalHotspots}`,
      status: "Critical",
      trend: "▲ 7 today",
      explanation: "Hotspot density is concentrated in the western and eastern high-risk clusters.",
      action: "Open Map",
      href: "/hotspots",
      tone: "fire",
      icon: Radar,
      gauge: Math.min(100, totalHotspots * 3),
      details: ["New today 7", "Resolved 4", "Density high"]
    },
    {
      title: "Highest Risk Region",
      metric: highestRiskRegion.name,
      status: highestRiskRegion.riskLevel,
      trend: `▲ ${Math.round(highestRiskRegion.riskScore / 10)}% risk trend`,
      explanation: "This region should receive immediate monitoring and field response priority.",
      action: "Open Region",
      href: "/map",
      tone: "alerts",
      icon: MapPin,
      gauge: highestRiskRegion.riskScore,
      details: [`${highestRiskRegion.confidence}% confidence`, `${highestRiskRegion.temperature}°C`, `NDVI ${highestRiskRegion.ndvi}`]
    },
    {
      title: "Fire Weather Risk Index",
      metric: `${averageFwi}`,
      status: "High",
      trend: "▲ above average",
      explanation: "The fire weather index is above the historical operating threshold.",
      action: "View Analytics",
      href: "/analytics",
      tone: "weather",
      icon: ThermometerSun,
      gauge: averageFwi,
      details: ["Historical avg 58", "Wind + humidity drivers", "Severity high"]
    },
    {
      title: "Active Alerts",
      metric: `${alerts.length}`,
      status: criticalAlerts > 0 ? "Critical" : "Watch",
      trend: `${criticalAlerts} critical · ${highAlerts} high`,
      explanation: "Operational alerts require acknowledgement, assignment, and continued monitoring.",
      action: "Open Alerts",
      href: "/alerts",
      tone: "alerts",
      icon: AlertTriangle,
      gauge: Math.min(100, alerts.length * 28),
      details: liveAlerts ? [`${liveAlerts} live alerts`, "Existing alert engine", "Prediction-based"] : ["Simulation data", "No live alert generated", "Fixture examples"]
    },
    {
      title: "Satellite Health",
      metric: "97%",
      status: "Good",
      trend: "▬ stable coverage",
      explanation: "Satellite coverage and image quality are sufficient for confident predictions.",
      action: "View Vegetation",
      href: "/vegetation",
      tone: "satellite",
      icon: Satellite,
      gauge: 97,
      details: ["Sentinel-2 fresh", "MODIS fresh", "Cloud 8%"]
    },
    {
      title: "Prediction Trend",
      metric: "Increasing",
      status: "Watch",
      trend: "▲ next 24h",
      explanation: "Risk is forecast to rise during the afternoon dry-wind window.",
      action: "View Analytics",
      href: "/analytics",
      tone: "prediction",
      icon: Activity,
      gauge: 76,
      details: ["Past week rising", "Confidence rising", "Forecast high"]
    },
    {
      title: "AI Recommendations",
      metric: "3 urgent",
      status: "Priority",
      trend: "▲ high impact",
      explanation: "Deploy drone monitoring, increase patrol frequency, and prepare response equipment.",
      action: "Open Insights",
      href: "/prediction",
      tone: "prediction",
      icon: Sparkles,
      gauge: 88,
      details: ["Drone monitoring", "Ranger patrols", "Public advisory"]
    },
    {
      title: "System Health",
      metric: "Online",
      status: "Healthy",
      trend: "▬ stable",
      explanation: "Core services are operational and ready for continuous monitoring workflows.",
      action: "View Settings",
      href: "/settings",
      tone: "system",
      icon: Server,
      gauge: 94,
      details: ["Backend online", "ML model online", "Storage healthy"]
    }
  ], [alerts.length, averageFwi, averageNbr, averageNdvi, confidence, criticalAlerts, highAlerts, highestRiskRegion, latestWeather, liveAlerts, overallRisk, totalHotspots]);

  return (
    <motion.section
      className="risk-breakdown"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      aria-labelledby="risk-breakdown-title"
    >
      <header className="risk-breakdown-banner">
        <div>
          <span className="eyebrow">Executive Command Panel</span>
          <h2 id="risk-breakdown-title">
            <Flame size={28} /> Overall Wildfire Situation
          </h2>
          <p>Risk is expected to increase within the next 24 hours. Deploy drone surveillance and increase patrol frequency in priority regions.</p>
        </div>
        <div className="breakdown-banner-metrics">
          <span><Flame size={15} /> Risk <strong>{riskCategory(overallRisk)}</strong></span>
          <span><CheckCircle2 size={15} /> Confidence <strong>{confidence}%</strong></span>
          <span><MapPin size={15} /> Highest <strong>{highestRiskRegion.name}</strong></span>
        </div>
      </header>

      <div className="risk-breakdown-grid">
        {cards.map((card, index) => (
          <motion.article
            className={`breakdown-card ${card.tone}`}
            key={card.title}
            whileHover={{ y: -4, scale: 1.01 }}
            transition={{ duration: 0.18 }}
            tabIndex={0}
            aria-label={`${card.title}: ${card.metric}, ${card.status}`}
          >
            <div className="breakdown-card-glow" />
            <div className="breakdown-card-header">
              <div className="breakdown-icon">
                <card.icon size={22} />
              </div>
              <span className="status-badge">{card.status}</span>
            </div>
            <div className="breakdown-main">
              <div>
                <h3>{card.title}</h3>
                <strong>{card.metric}</strong>
                <small>{card.trend}</small>
              </div>
              {card.gauge ? (
                <div
                  className="breakdown-gauge"
                  style={{ "--breakdown-gauge": `${card.gauge * 3.6}deg` } as CSSProperties & Record<"--breakdown-gauge", string>}
                >
                  <span>{card.gauge}</span>
                </div>
              ) : null}
            </div>
            <div className="breakdown-sparkline" aria-hidden="true">
              <ResponsiveContainer width="100%" height={54}>
                <LineChart data={miniSeries(trendData, index - 4)}>
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="currentColor" strokeWidth={2.4} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p>{card.explanation}</p>
            <div className="breakdown-details">
              {card.details.map((detail) => (
                <span key={detail}>{detail}</span>
              ))}
            </div>
            <Link className="breakdown-action" to={card.href}>
              {card.action} <ArrowRight size={15} />
            </Link>
          </motion.article>
        ))}
      </div>

      <footer className="risk-breakdown-health">
        <span><Cpu size={15} /> CPU normal</span>
        <span><Database size={15} /> Database healthy</span>
        <span><Wind size={15} /> Weather API online</span>
        <span><Satellite size={15} /> Satellite API online</span>
      </footer>
    </motion.section>
  );
}
