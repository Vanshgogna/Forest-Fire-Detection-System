import { AlertTriangle, Gauge, Leaf, Satellite } from "lucide-react";
import { AlertList } from "../components/alerts/AlertList";
import { MetricCard } from "../components/common/MetricCard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { PredictionSummary } from "../components/dashboard/PredictionSummary";
import { RegionTable } from "../components/dashboard/RegionTable";
import { RiskMap } from "../components/dashboard/RiskMap";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";

export function DashboardPage() {
  const { data, isLoading, isFetching } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Loading environmental intelligence...</div>;

  const selectedRegion = data.regions.find((region) => region.id === selectedRegionId) ?? data.regions[0];
  const selectedWeatherData = data.weatherDataByRegion?.[selectedRegion.id] ?? data.weatherData;
  const riskAvailable = selectedRegion.riskStatus !== "unavailable";
  const vegetationAvailable = selectedRegion.vegetationSource?.status === "live" || selectedRegion.vegetationSource?.status === "degraded";
  const hotspotAvailable = selectedRegion.hotspotSource?.status === "live";
  const weatherDetail = selectedRegion.weatherSource?.message ?? data.provenance.weather.message ?? data.provenance.weather.provider;
  const weatherStatus = selectedRegion.weatherSource?.dataStatus ?? (selectedRegion.weatherSource?.status === "live" ? "LIVE" : "UNAVAILABLE");
  const hotspotDetail = selectedRegion.hotspotSource?.message ?? "Hotspot data unavailable";
  const riskDetail = selectedRegion.riskSource?.message ?? "Live prediction unavailable";
  const showingLiveAlerts = data.alerts.some((alert) => alert.source === "live_prediction");
  const selectedAlerts = data.alerts.filter((alert) => alert.region === selectedRegion.name);

  return (
    <>
      <PageHeader
        eyebrow={`Command Dashboard · ${selectedRegion.name}`}
        title="Wildfire Risk Operations"
        description={isFetching ? "Refreshing live environmental intelligence for the selected region." : "Current risk, active hotspots, satellite coverage, and priority response areas."}
      />
      <section className="metric-grid">
        <MetricCard label="Fire Risk" value={riskAvailable ? `${selectedRegion.riskScore}%` : "Unavailable"} detail={riskDetail} trend="flat" icon={Gauge} tone={riskAvailable ? "danger" : "warning"} />
        <MetricCard label="NDVI / NBR" value={vegetationAvailable ? `${selectedRegion.ndvi.toFixed(3)} / ${selectedRegion.nbr.toFixed(3)}` : "Unavailable"} detail={selectedRegion.vegetationSource?.message ?? "Sentinel NDVI unavailable"} trend="flat" icon={Leaf} tone="warning" />
        <MetricCard label="Active Hotspots" value={hotspotAvailable ? `${selectedRegion.hotspots}` : "Unavailable"} detail={hotspotDetail} trend="flat" icon={AlertTriangle} tone="danger" />
        <MetricCard label="Weather Source" value={weatherStatus} detail={weatherDetail} trend="flat" icon={Satellite} tone={weatherStatus === "LIVE" ? "success" : weatherStatus === "UNAVAILABLE" ? "warning" : "neutral"} />
      </section>
      <PredictionSummary regions={[selectedRegion]} trendData={data.trendData} weatherData={selectedWeatherData} weatherSource={selectedRegion.weatherSource ?? data.provenance.weather} />
      <section className="dashboard-grid">
        <Panel title="GIS Risk Surface" subtitle={`${selectedRegion.name} in context with monitored forest regions`}>
          <RiskMap regions={data.regions} />
        </Panel>
        <Panel title="Active Alerts" subtitle={showingLiveAlerts ? `Alerts for ${selectedRegion.name} from the existing alert engine` : `No live alert generated for ${selectedRegion.name}`}>
          {selectedAlerts.length ? <AlertList alerts={selectedAlerts} /> : <div className="alert-empty-state">No active alerts for {selectedRegion.name}</div>}
        </Panel>
      </section>
      <Panel title="Regional Intelligence Table" subtitle="Operational summary for forest divisions">
        <RegionTable regions={data.regions} />
      </Panel>
    </>
  );
}
