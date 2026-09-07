import { Download, Maximize2, RefreshCcw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { RegionalBarChart } from "../components/charts/RegionalBarChart";
import { RiskTrendChart } from "../components/charts/RiskTrendChart";
import { WeatherChart } from "../components/charts/WeatherChart";
import { RiskDistributionDashboard } from "../components/analytics/RiskDistributionDashboard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { ENVIRONMENTAL_QUERY_KEY, useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";
import { buildRegionsCsv, downloadTextFile, safeFileNamePart } from "../utils/downloads";

export function AnalyticsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Preparing analytics dashboard...</div>;
  const region = data.regions.find((item) => item.id === selectedRegionId) ?? data.regions[0];
  const weatherAvailable = region.weatherSource?.status === "live" || region.weatherSource?.status === "degraded";
  const selectedWeatherData = weatherAvailable ? data.weatherDataByRegion?.[region.id] ?? data.weatherData : [];
  const exportAnalytics = () => {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadTextFile(
      `firesight-analytics-${safeFileNamePart(region.name)}-${stamp}.csv`,
      buildRegionsCsv(data.regions, selectedWeatherData),
      "text/csv;charset=utf-8"
    );
  };
  const requestFullscreen = () => {
    void document.documentElement.requestFullscreen?.();
  };

  return (
    <>
      <PageHeader
        eyebrow={`Analytics Dashboard · ${region.name}`}
        title="AI-Powered Environmental Intelligence"
        description={`Weather uses ${data.provenance.weather.provider}; environmental and prediction data refresh with the selected region.`}
        actions={
          <div className="action-row">
            <button className="button secondary" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY })}><RefreshCcw size={16} /> Refresh</button>
            <button className="button secondary" type="button" onClick={requestFullscreen}><Maximize2 size={16} /> Fullscreen</button>
            <button className="button primary" type="button" onClick={exportAnalytics}><Download size={16} /> Export</button>
          </div>
        }
      />
      <RiskDistributionDashboard regions={data.regions} trendData={data.trendData} weatherData={selectedWeatherData} />
      <section className="analytics-grid">
        <Panel title="Fire Risk Trend" subtitle="Development trend fixture, not live backend history">
          <RiskTrendChart data={data.trendData} />
        </Panel>
        <Panel title="Weather Trends" subtitle="Forecasted fire weather drivers">
          <WeatherChart data={selectedWeatherData} />
        </Panel>
        <Panel title="Regional Comparison" subtitle="Risk and confidence by forest division">
          <RegionalBarChart data={data.regions} />
        </Panel>
        <Panel title="Data Status Notes" subtitle="Provider status for the selected region">
          <div className="annotation-card">
            <strong>Selected region inputs</strong>
            <p>
              Weather {region.weatherSource?.dataStatus ?? "UNAVAILABLE"} · Sentinel-2 {region.vegetationSource?.dataStatus ?? "UNAVAILABLE"} · FIRMS {region.hotspotSource?.dataStatus ?? "UNAVAILABLE"} · Prediction {region.riskSource?.dataStatus ?? "UNAVAILABLE"}.
            </p>
          </div>
          <div className="annotation-card">
            <strong>Weather provenance</strong>
            <p>{data.provenance.weather.message ?? "Live weather provenance is attached to the current weather response."}</p>
          </div>
        </Panel>
      </section>
    </>
  );
}
