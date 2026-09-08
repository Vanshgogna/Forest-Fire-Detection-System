import { BrainCircuit, Gauge, ShieldAlert, Sparkles } from "lucide-react";
import { MetricCard } from "../components/common/MetricCard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { RegionTable } from "../components/dashboard/RegionTable";
import { ExplainabilityDashboard } from "../components/prediction/ExplainabilityDashboard";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";
import { hasProviderData, sourceStatusLabel } from "../utils/risk";

export function PredictionPage() {
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Running prediction model...</div>;
  const region = data.regions.find((item) => item.id === selectedRegionId) ?? data.regions[0];
  const weatherAvailable = hasProviderData(region.weatherSource?.status);
  const selectedWeatherData = weatherAvailable ? data.weatherDataByRegion?.[region.id] ?? data.weatherData : [];
  const predictionAvailable = region.riskStatus !== "unavailable";
  const predictionDetail = region.riskSource?.message ?? "Live prediction unavailable";
  const predictionModeLabel = region.riskStatus === "live" ? "live model output" : region.riskStatus === "simulation" ? "simulation output" : "No fake live score shown";
  const weatherStatus = sourceStatusLabel(region.weatherSource);

  return (
    <>
      <PageHeader eyebrow={`Machine Learning · ${region.name}`} title="Risk Prediction Engine" description={predictionDetail} />
      <section className="metric-grid">
        <MetricCard label="Prediction Confidence" value={predictionAvailable ? `${region.confidence}%` : "Unavailable"} detail={predictionDetail} trend="flat" icon={BrainCircuit} tone={predictionAvailable ? "success" : "warning"} />
        <MetricCard label="Risk Score" value={predictionAvailable ? `${region.riskScore}/100` : "Unavailable"} detail={predictionAvailable ? `${region.riskLevel} ${predictionModeLabel}` : predictionModeLabel} trend="flat" icon={ShieldAlert} tone={predictionAvailable ? "danger" : "warning"} />
        <MetricCard label="Weather Source" value={weatherStatus} detail={region.weatherSource?.message ?? region.weatherSource?.provider ?? data.provenance.weather.provider} trend="flat" icon={Gauge} tone={weatherStatus === "LIVE" ? "success" : weatherStatus === "UNAVAILABLE" ? "warning" : "neutral"} />
        <MetricCard label="AI Insights" value={region.prediction?.recommendations?.length ? `${region.prediction.recommendations.length}` : "Unavailable"} detail={region.prediction?.explanation ?? "Backend explanation unavailable"} trend="flat" icon={Sparkles} tone="neutral" />
      </section>
      <ExplainabilityDashboard regions={data.regions} trendData={data.trendData} weatherData={selectedWeatherData} selectedRegionId={region.id} />
      <Panel title="Explainable Prediction Summary" subtitle="Model factors translated into operational language">
        <div className="insight-list">
          <article><strong>Prediction status</strong><span>{predictionAvailable ? "Live backend prediction is available for this region." : predictionDetail}</span></article>
          <article><strong>Data status</strong><span>{region.prediction?.missing_sources?.map((item) => `${item.source}: ${item.status}`).join(" · ") || "Required environmental inputs are available."}</span></article>
          <article><strong>Recommended action</strong><span>{region.prediction?.recommendations?.[0] ?? "No live recommendation until prediction is available."}</span></article>
        </div>
      </Panel>
      <Panel title="Regional Prediction Output">
        <RegionTable regions={data.regions} />
      </Panel>
    </>
  );
}
