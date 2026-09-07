import { Activity, CalendarClock, Satellite, ShieldCheck } from "lucide-react";
import { MetricCard } from "../components/common/MetricCard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";

export function VegetationPage() {
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Loading vegetation analytics...</div>;
  const region = data.regions.find((item) => item.id === selectedRegionId) ?? data.regions[0];
  const vegetationDetail = region.vegetationSource?.message ?? data.provenance.vegetation.message ?? "Vegetation data unavailable";
  const scene = region.sentinelScene;
  const capturedAt = scene?.captured_at ? new Date(scene.captured_at).toLocaleDateString() : "No scene";
  const rasterStatus = scene?.raster_processing?.status ?? "UNAVAILABLE";
  const qualityStatus = scene?.quality_masking?.status ?? "UNAVAILABLE";
  const ndviStatus = scene?.ndvi_processing?.status ?? "UNAVAILABLE";
  const ndviMean = ndviStatus === "READY" && typeof scene?.ndvi_processing?.mean === "number" ? scene.ndvi_processing.mean.toFixed(3) : "Unavailable";
  const validPixels = typeof scene?.quality_masking?.valid_pixel_percentage === "number" ? `${Math.round(scene.quality_masking.valid_pixel_percentage)}% valid` : capturedAt;
  const ndviCoverage = typeof scene?.ndvi_processing?.valid_pixel_percentage === "number" ? `${Math.round(scene.ndvi_processing.valid_pixel_percentage)}% coverage` : "NDVI data unavailable";

  return (
    <>
      <PageHeader eyebrow={`Remote Sensing · ${region.name}`} title="Vegetation Analysis" description={vegetationDetail} />
      <section className="metric-grid four">
        <MetricCard label="Scene Status" value={scene?.acquisition_status ?? "Unavailable"} detail={scene?.provider ?? "Sentinel-2"} trend="flat" icon={Satellite} tone={scene?.available ? "success" : "warning"} />
        <MetricCard label="Raster Prep" value={rasterStatus} detail={capturedAt} trend="flat" icon={CalendarClock} tone={rasterStatus === "READY" ? "success" : "neutral"} />
        <MetricCard label="Quality Mask" value={qualityStatus} detail={validPixels} trend="flat" icon={ShieldCheck} tone={qualityStatus === "READY" ? "success" : qualityStatus === "LOW_QUALITY" ? "warning" : "neutral"} />
        <MetricCard label="NDVI Mean" value={ndviMean} detail={ndviCoverage} trend="flat" icon={Activity} tone={ndviStatus === "READY" ? "success" : ndviStatus === "LOW_QUALITY" ? "warning" : "neutral"} />
      </section>
      <Panel title="Regional Sentinel Scene Status">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Region</th>
                <th>Status</th>
                <th>Scene</th>
                <th>Raster Prep</th>
                <th>Quality Mask</th>
                <th>NDVI</th>
                <th>Valid Pixels</th>
                <th>Captured</th>
              </tr>
            </thead>
            <tbody>
              {data.regions.map((item) => {
                const itemScene = item.sentinelScene;
                return (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.name}</strong>
                      <span>{item.state}</span>
                    </td>
                    <td>{itemScene?.acquisition_status ?? "UNAVAILABLE"}</td>
                    <td>{itemScene?.scene_id ?? "No acquired Sentinel-2 scene"}</td>
                    <td>{itemScene?.raster_processing?.status ?? "UNAVAILABLE"}</td>
                    <td>{itemScene?.quality_masking?.status ?? "UNAVAILABLE"}</td>
                    <td>{itemScene?.ndvi_processing?.status === "READY" && typeof itemScene.ndvi_processing.mean === "number" ? itemScene.ndvi_processing.mean.toFixed(3) : "Unavailable"}</td>
                    <td>{typeof itemScene?.ndvi_processing?.valid_pixel_percentage === "number" ? `${Math.round(itemScene.ndvi_processing.valid_pixel_percentage)}%` : "Unavailable"}</td>
                    <td>{itemScene?.captured_at ? new Date(itemScene.captured_at).toLocaleDateString() : "Unavailable"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
