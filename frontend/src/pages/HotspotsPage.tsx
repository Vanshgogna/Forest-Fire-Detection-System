import { Flame, MapPin, RadioTower } from "lucide-react";
import { AlertList } from "../components/alerts/AlertList";
import { RegionalBarChart } from "../components/charts/RegionalBarChart";
import { MetricCard } from "../components/common/MetricCard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";
import { hasProviderData } from "../utils/risk";

export function HotspotsPage() {
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Loading hotspot stream...</div>;
  const region = data.regions.find((item) => item.id === selectedRegionId) ?? data.regions[0];
  const hotspotDetail = region.hotspotSource?.message ?? data.provenance.hotspots.message ?? "Hotspot data unavailable";
  const hotspotAvailable = hasProviderData(region.hotspotSource?.status);
  const sourceLabel = hotspotAvailable ? "FIRMS" : "Unavailable";
  const showingLiveAlerts = data.alerts.some((alert) => alert.source === "live_prediction");
  const selectedAlerts = data.alerts.filter((alert) => alert.region === region.name);

  return (
    <>
      <PageHeader eyebrow={`Fire Monitoring · ${region.name}`} title="Fire Hotspot Detection" description={hotspotDetail} />
      <section className="metric-grid three">
        <MetricCard label="Active Hotspots" value={hotspotAvailable ? region.hotspots.toString() : "Unavailable"} detail={hotspotDetail} trend="flat" icon={Flame} tone="danger" />
        <MetricCard label="FIRMS Detections" value={`${region.hotspotDetections?.length ?? 0}`} detail="database-backed active-fire observations" trend="flat" icon={MapPin} tone="danger" />
        <MetricCard label="Hotspot Source" value={sourceLabel} detail={region.hotspotSource?.provider ?? "nasa-firms"} trend="flat" icon={RadioTower} tone="neutral" />
      </section>
      <section className="dashboard-grid">
        <Panel title="Hotspot Distribution" subtitle="Regional fire anomaly comparison">
          <RegionalBarChart data={data.regions} />
        </Panel>
        <Panel title="Related Warnings" subtitle={showingLiveAlerts ? `Prediction alerts for ${region.name}` : `No live alert generated for ${region.name}`}>
          {selectedAlerts.length ? <AlertList alerts={selectedAlerts} /> : <div className="alert-empty-state">No active alerts for {region.name}</div>}
        </Panel>
      </section>
    </>
  );
}
