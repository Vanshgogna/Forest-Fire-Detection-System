import { CloudRain, CloudSun, ThermometerSun, Wind } from "lucide-react";
import { WeatherChart } from "../components/charts/WeatherChart";
import { MetricCard } from "../components/common/MetricCard";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";

export function WeatherPage() {
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Loading weather intelligence...</div>;
  const region = data.regions.find((item) => item.id === selectedRegionId) ?? data.regions[0];
  const source = region.weatherSource ?? data.provenance.weather;
  const dataStatus = source.dataStatus ?? (source.status === "live" ? "LIVE" : source.status === "unavailable" ? "UNAVAILABLE" : "SUSPICIOUS");
  const updatedDetail = source.message ?? "source timestamp unavailable";
  const locationName = source.location?.region ?? region.name;
  const coordinates = source.location ? `${source.location.latitude}, ${source.location.longitude}` : `${region.coordinates[0]}, ${region.coordinates[1]}`;
  const weatherAvailable = source.status === "live" || source.status === "degraded";
  const selectedWeatherData = weatherAvailable ? data.weatherDataByRegion?.[region.id] ?? data.weatherData : [];

  return (
    <>
      <PageHeader eyebrow={`Weather Analysis · ${region.name}`} title="Fire Weather Conditions" description="Current weather is fetched by forest-region coordinates and shown with provenance." />
      <section className="metric-grid">
        <MetricCard label="Temperature" value={weatherAvailable ? `${region.temperature}°C` : "Unavailable"} detail="air temperature at 2m" trend="flat" icon={ThermometerSun} tone={weatherAvailable ? "danger" : "warning"} />
        <MetricCard label="Humidity" value={weatherAvailable ? `${region.humidity}%` : "Unavailable"} detail={source.provider} trend="flat" icon={CloudSun} tone={weatherAvailable ? "warning" : "neutral"} />
        <MetricCard label="Wind Speed" value={weatherAvailable ? `${region.windSpeed} km/h` : "Unavailable"} detail={source.provider} trend="flat" icon={Wind} tone={weatherAvailable ? "warning" : "neutral"} />
        <MetricCard label="Rainfall" value={weatherAvailable ? `${region.rainfall} mm` : "Unavailable"} detail={source.provider} trend="flat" icon={CloudRain} tone={weatherAvailable ? "danger" : "neutral"} />
      </section>
      <section className="weather-source-strip" aria-label="Weather source provenance">
        <span><strong>Source</strong>{source.provider}</span>
        <span><strong>Location</strong>{locationName}</span>
        <span><strong>Coordinates</strong>{coordinates}</span>
        <span><strong>Updated</strong>{updatedDetail}</span>
        <span><strong>Data status</strong>{dataStatus}</span>
      </section>
      <details className="weather-provenance-panel">
        <summary>Weather provenance details</summary>
        <dl>
          <div><dt>Displayed variable</dt><dd>Open-Meteo `temperature_2m`, air temperature at 2 meters above ground.</dd></div>
          <div><dt>Coordinate method</dt><dd>{source.location?.coordinate_method ?? "configured representative point"}</dd></div>
          <div><dt>Observed at</dt><dd>{source.observedAt ?? "unavailable"}</dd></div>
          <div><dt>Retrieved at</dt><dd>{source.retrievedAt ?? "unavailable"}</dd></div>
          <div><dt>Cache</dt><dd>{source.cacheStatus ?? "not available"}</dd></div>
          <div><dt>Units</dt><dd>°C, km/h, mm, hPa</dd></div>
        </dl>
      </details>
      <Panel title="Forecast Drivers" subtitle="Temperature, humidity, and Fire Weather Risk Index">
        <WeatherChart data={selectedWeatherData} />
      </Panel>
    </>
  );
}
