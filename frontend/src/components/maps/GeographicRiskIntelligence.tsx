import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  CloudSun,
  Compass,
  Crosshair,
  Download,
  Expand,
  Flame,
  Gauge,
  LocateFixed,
  Map as MapIcon,
  Mountain,
  RefreshCcw,
  Satellite,
  Search,
  Trees,
  Wind
} from "lucide-react";
import { CircleMarker, MapContainer, Polygon, Popup, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { RegionRisk, TrendPoint, WeatherSnapshot } from "../../types";
import { getRiskColor, hasProviderData, sourceStatusLabel } from "../../utils/risk";
import { useEnvironmentalContext } from "../../contexts/EnvironmentalContext";
import { ENVIRONMENTAL_QUERY_KEY } from "../../hooks/useEnvironmentalData";
import { buildRegionsCsv, buildRegionsGeoJson, downloadTextFile } from "../../utils/downloads";

interface GeographicRiskIntelligenceProps {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherData: WeatherSnapshot[];
}

const baseMaps = [
  { label: "OpenStreetMap", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" },
  { label: "Light", url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" },
  { label: "Dark", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" },
  { label: "Topographic", url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png" }
];

function regionPolygon(region: RegionRisk): [number, number][] {
  const [lat, lng] = region.coordinates;
  const spread = 0.45 + (hasPrediction(region) ? region.riskScore : 0) / 240;
  return [
    [lat + spread, lng - spread * 0.8],
    [lat + spread * 0.6, lng + spread],
    [lat - spread * 0.7, lng + spread * 0.85],
    [lat - spread, lng - spread * 0.55]
  ];
}

function matrixPosition(region: RegionRisk) {
  const likelihood = Math.min(5, Math.max(1, Math.ceil((hasPrediction(region) ? region.riskScore : 0) / 20)));
  const weatherPressure = hasProviderData(region.weatherSource?.status) ? region.windSpeed + region.temperature : 0;
  const hotspotPressure = hasProviderData(region.hotspotSource?.status) ? region.hotspots * 3 : 0;
  const impact = Math.min(5, Math.max(1, Math.ceil((hotspotPressure + weatherPressure) / 20)));
  return { likelihood, impact };
}

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function hasPrediction(region: RegionRisk) {
  return region.riskStatus !== "unavailable";
}

function riskText(region: RegionRisk) {
  return hasPrediction(region) ? `${region.riskScore}` : "Unavailable";
}

function nbrText(region: RegionRisk) {
  if (!hasPrediction(region)) return "NBR unavailable";
  return region.prediction?.defaulted_features?.includes("nbr") ? `NBR defaulted ${region.nbr}` : `NBR ${region.nbr}`;
}

export function GeographicRiskIntelligence({ regions, trendData, weatherData }: GeographicRiskIntelligenceProps) {
  const queryClient = useQueryClient();
  const [baseMapIndex, setBaseMapIndex] = useState(0);
  const { selectedRegionId, setSelectedRegionId } = useEnvironmentalContext();
  const [opacity, setOpacity] = useState(72);
  const [intensity, setIntensity] = useState(84);
  const selectedRegion = useMemo(() => regions.find((region) => region.id === selectedRegionId) ?? regions[0], [regions, selectedRegionId]);
  const selectedWeatherAvailable = hasProviderData(selectedRegion.weatherSource?.status);
  const selectedWeatherStatus = sourceStatusLabel(selectedRegion.weatherSource);
  const rankedRegions = useMemo(() => [...regions].sort((a, b) => (hasPrediction(b) ? b.riskScore : -1) - (hasPrediction(a) ? a.riskScore : -1)), [regions]);
  const regionShapes = useMemo(
    () =>
      regions.map((region) => {
        const color = hasPrediction(region) ? getRiskColor(region.riskLevel) : "var(--muted)";
        return {
          region,
          color,
          polygon: regionPolygon(region),
          hotspots: (region.hotspotDetections ?? []).slice(0, 50).map((hotspot) => ({
            id: hotspot.source_record_id ?? `${region.id}-${hotspot.detected_at}-${hotspot.latitude}-${hotspot.longitude}`,
            center: [hotspot.latitude, hotspot.longitude] as [number, number],
            radius: (5 + hotspot.confidence / 18) * (0.7 + intensity / 100),
            confidence: hotspot.confidence,
            detectedAt: hotspot.detected_at,
            satellite: hotspot.satellite,
            instrument: hotspot.instrument
          }))
        };
      }),
    [regions, intensity]
  );
  const spatialStats = useMemo(
    () => {
      const liveVegetationRegions = regions.filter((region) => hasProviderData(region.vegetationSource?.status));
      const averageNdvi = liveVegetationRegions.length ? average(liveVegetationRegions.map((region) => region.ndvi)).toFixed(2) : "Unavailable";
      const predictedRegions = regions.filter(hasPrediction);
      const liveHotspotRegions = regions.filter((region) => hasProviderData(region.hotspotSource?.status));
      const highRiskRegions = predictedRegions.filter((region) => region.riskScore >= 60).length;
      const hotspotCount = liveHotspotRegions.length ? `${liveHotspotRegions.reduce((sum, region) => sum + region.hotspots, 0)}` : "Unavailable";
      return [
      ["Monitored Regions", `${regions.length}`, Trees],
      ["High Risk Regions", predictedRegions.length ? `${highRiskRegions}` : "Unavailable", Flame],
      ["Average NDVI", averageNdvi, Satellite],
      ["Prediction Coverage", predictedRegions.length ? `${predictedRegions.length}/${regions.length}` : "Unavailable", Gauge],
      ["Weather Overlay", selectedWeatherAvailable ? selectedWeatherStatus : "Unavailable", CloudSun],
      ["FIRMS 24h Detections", hotspotCount, Activity],
      ["Vegetation Coverage", liveVegetationRegions.length ? "Available" : "Unavailable", Trees],
      ["Satellite Coverage", liveVegetationRegions.length ? "Available" : "Unavailable", Satellite]
    ];
    },
    [regions, selectedWeatherAvailable, selectedWeatherStatus]
  );
  const goHome = () => {
    setBaseMapIndex(0);
    setSelectedRegionId(regions[0]?.id ?? selectedRegion.id);
  };
  const requestMapFullscreen = () => {
    void document.querySelector(".geo-map-shell")?.requestFullscreen?.();
  };
  const exportGeoJson = () => {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadTextFile(`firesight-regions-${stamp}.geojson`, buildRegionsGeoJson(regions), "application/geo+json;charset=utf-8");
  };
  const exportCsv = () => {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadTextFile(`firesight-regional-risk-${stamp}.csv`, buildRegionsCsv(regions, weatherData), "text/csv;charset=utf-8");
  };
  const selectedRegionInsight = hasPrediction(selectedRegion)
    ? `${selectedRegion.name} is currently assessed at ${selectedRegion.riskLevel.toLowerCase()} risk with ${hasProviderData(selectedRegion.hotspotSource?.status) ? `${selectedRegion.hotspots} active hotspot${selectedRegion.hotspots === 1 ? "" : "s"}` : "no live hotspot count available"}.`
    : `${selectedRegion.name} does not have a live prediction available yet, so field decisions should wait for provider recovery or use direct observations.`;
  const weatherVegetationInsight = hasProviderData(selectedRegion.vegetationSource?.status)
    ? `Risk context for ${selectedRegion.name} includes ${selectedWeatherAvailable ? "weather inputs," : "no available weather inputs,"} NDVI ${selectedRegion.ndvi}, and NBR ${selectedRegion.nbr}.`
    : `Vegetation indicators for ${selectedRegion.name} are unavailable, so the map is showing weather and hotspot context only.`;
  const liveHotspotClusters = rankedRegions.filter((region) => hasProviderData(region.hotspotSource?.status) && region.hotspots > 0);
  const recommendations = rankedRegions.slice(0, 5).map((region) => {
    if (!hasPrediction(region)) return `Review provider status for ${region.name} before dispatch planning.`;
    if (hasProviderData(region.hotspotSource?.status) && region.hotspots > 0) {
      return `Verify ${region.hotspots} hotspot${region.hotspots === 1 ? "" : "s"} in ${region.name} with field or satellite confirmation.`;
    }
    return `Continue weather and vegetation monitoring for ${region.name}.`;
  });

  return (
    <motion.section
      className="geo-intelligence"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      aria-labelledby="geo-intelligence-title"
    >
      <header className="geo-header">
        <div>
          <span className="eyebrow">Geographic Risk Intelligence</span>
          <h2 id="geo-intelligence-title"><MapIcon size={30} /> Spatial Wildfire Command Center</h2>
          <p>AI prediction, GIS visualization, weather intelligence, satellite indicators, hotspot density, and regional response priorities in one synchronized view.</p>
        </div>
        <div className="geo-toolbar">
          <button type="button" onClick={goHome}><LocateFixed size={15} /> Home</button>
          <button type="button" onClick={requestMapFullscreen}><Expand size={15} /> Fullscreen</button>
          <button type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ENVIRONMENTAL_QUERY_KEY })}><RefreshCcw size={15} /> Refresh</button>
          <button type="button" onClick={exportGeoJson}><Download size={15} /> Export GeoJSON</button>
        </div>
      </header>

      <div className="geo-command-grid">
        <section className="geo-map-panel">
          <div className="geo-map-controls">
            <div className="base-map-switcher">
              {baseMaps.map((map, index) => (
                <button className={index === baseMapIndex ? "active" : ""} key={map.label} type="button" onClick={() => setBaseMapIndex(index)}>
                  {map.label}
                </button>
              ))}
            </div>
            <div className="coordinate-inspector">
              <Compass size={15} />
              <span>{selectedRegion.coordinates[0].toFixed(3)}, {selectedRegion.coordinates[1].toFixed(3)}</span>
              <span>{selectedRegion.state}</span>
              <span>Risk {riskText(selectedRegion)}</span>
            </div>
          </div>

          <div className="geo-map-shell">
            <MapContainer center={[21.5, 79]} zoom={5} scrollWheelZoom className="geo-risk-map">
              <TileLayer attribution="&copy; OpenStreetMap contributors" url={baseMaps[baseMapIndex].url} />
              {regionShapes.map(({ region, color, polygon }) => {
                return (
                  <Polygon
                    key={region.id}
                    positions={polygon}
                    pathOptions={{
                      color,
                      fillColor: color,
                      fillOpacity: Math.min(0.75, (opacity / 180) * (0.65 + intensity / 100)),
                      weight: selectedRegion.id === region.id ? 4 : 2
                    }}
                    eventHandlers={{ click: () => setSelectedRegionId(region.id) }}
                  >
                    <Tooltip sticky>
                      <strong>{region.name}</strong>
                      <br />
                      {hasPrediction(region) ? `Risk ${region.riskScore} · Confidence ${region.confidence}%` : "Live prediction unavailable"}
                      <br />
                      {hasProviderData(region.vegetationSource?.status) ? `NDVI ${region.ndvi}` : "NDVI unavailable"}
                    </Tooltip>
                    <Popup>
                      <strong>{region.name}</strong>
                      <br />
                      {hasPrediction(region) ? `${region.riskLevel} risk` : "Live prediction unavailable"} · {hasProviderData(region.hotspotSource?.status) ? `${region.hotspots} active hotspots` : "hotspots unavailable"}.
                    </Popup>
                  </Polygon>
                );
              })}
              {regionShapes.map(({ region, hotspots }) =>
                hotspots.map((hotspot) => (
                  <CircleMarker
                    key={hotspot.id}
                    center={hotspot.center}
                    radius={hotspot.radius}
                    pathOptions={{ color: "#e53935", fillColor: "#e53935", fillOpacity: 0.52, weight: 1 }}
                  >
                    <Tooltip>
                      FIRMS active-fire detection · {Math.round(hotspot.confidence)}% confidence
                      <br />
                      {region.name} · {hotspot.satellite ?? "satellite"} {hotspot.instrument ?? ""}
                    </Tooltip>
                  </CircleMarker>
                ))
              )}
            </MapContainer>
          </div>

          <div className="geo-map-footer">
            <label>Heatmap opacity <input type="range" min="20" max="100" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /></label>
            <label>Risk intensity <input type="range" min="20" max="100" value={intensity} onChange={(event) => setIntensity(Number(event.target.value))} /></label>
            <div className="geo-legend">
              {["Low", "Moderate", "High", "Very High", "Extreme"].map((label, index) => (
                <span key={label}><i className={`risk-${index}`} /> {label}</span>
              ))}
            </div>
          </div>
        </section>

        <aside className="geo-side-panel">
          <section className="geo-card selected-region-card">
            <div className="geo-card-header">
              <h3><Crosshair size={17} /> Region Details</h3>
              <span>{hasPrediction(selectedRegion) ? selectedRegion.riskLevel : "Unavailable"}</span>
            </div>
            <strong>{selectedRegion.name}</strong>
            <div className="selected-region-metrics">
              <span>Prediction {riskText(selectedRegion)}</span>
              <span>Confidence {hasPrediction(selectedRegion) ? `${selectedRegion.confidence}%` : "Unavailable"}</span>
              <span>{hasProviderData(selectedRegion.vegetationSource?.status) ? `NDVI ${selectedRegion.ndvi}` : "NDVI unavailable"}</span>
              <span>{nbrText(selectedRegion)}</span>
              <span>{hasProviderData(selectedRegion.hotspotSource?.status) ? `${selectedRegion.hotspots} hotspots` : "Hotspots unavailable"}</span>
            </div>
          </section>

          <section className="geo-card">
            <div className="geo-card-header">
              <h3><CloudSun size={17} /> Weather Overlay</h3>
              <span>{selectedWeatherStatus}</span>
            </div>
            <div className="weather-overlay-grid">
              <span>Temp <strong>{selectedWeatherAvailable ? `${selectedRegion.temperature}°C` : "Unavailable"}</strong></span>
              <span>Wind <strong>{selectedWeatherAvailable ? `${selectedRegion.windSpeed} km/h` : "Unavailable"}</strong></span>
              <span>Humidity <strong>{selectedWeatherAvailable ? `${selectedRegion.humidity}%` : "Unavailable"}</strong></span>
              <span>Rainfall <strong>{selectedWeatherAvailable ? `${selectedRegion.rainfall} mm` : "Unavailable"}</strong></span>
            </div>
          </section>
        </aside>
      </div>

      <div className="geo-analytics-grid">
        <section className="geo-card matrix-card">
          <div className="geo-card-header">
            <h3><Gauge size={17} /> Risk Matrix</h3>
            <span>Likelihood x Impact</span>
          </div>
          <div className="geo-risk-matrix">
            {Array.from({ length: 25 }).map((_, index) => {
              const likelihood = (index % 5) + 1;
              const impact = 5 - Math.floor(index / 5);
              const cellRegions = regions.filter((region) => {
                const position = matrixPosition(region);
                return position.likelihood === likelihood && position.impact === impact;
              });
              return (
                <div className={`geo-matrix-cell level-${Math.min(5, Math.ceil((likelihood + impact) / 2))}`} key={`${likelihood}-${impact}`}>
                  {cellRegions.map((region) => <span key={region.id}>{region.name.slice(0, 2)}</span>)}
                </div>
              );
            })}
          </div>
          <div className="matrix-labels"><span>Impact: Negligible to Critical</span><span>Likelihood: Very Low to Very High</span></div>
        </section>

        <section className="geo-card stats-card">
          <div className="geo-card-header">
            <h3><BarChart3 size={17} /> Spatial Statistics</h3>
            <span>Auto refreshed</span>
          </div>
          <div className="spatial-stat-grid">
            {spatialStats.map(([label, value, Icon]) => (
              <article key={label as string}>
                <Icon size={18} />
                <span>{label as string}</span>
                <strong>{value as string}</strong>
              </article>
            ))}
          </div>
        </section>

        <section className="geo-card wide">
          <div className="geo-card-header">
            <h3><Search size={17} /> Regional Risk Distribution</h3>
            <button type="button" onClick={exportCsv}>Export CSV</button>
          </div>
          <div className="geo-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Risk Score</th>
                  <th>Prediction</th>
                  <th>Confidence</th>
                  <th>NDVI</th>
                  <th>NBR</th>
                  <th>Prediction Source</th>
                </tr>
              </thead>
              <tbody>
                {rankedRegions.map((region) => (
                  <tr key={region.id} onClick={() => setSelectedRegionId(region.id)}>
                    <td><strong>{region.name}</strong><span>{region.state}</span></td>
                    <td>{riskText(region)}</td>
                    <td>{hasPrediction(region) ? region.riskLevel : "Unavailable"}</td>
                    <td>{hasPrediction(region) ? `${region.confidence}%` : "Unavailable"}</td>
                    <td>{hasProviderData(region.vegetationSource?.status) ? region.ndvi : "Unavailable"}</td>
                    <td>{hasPrediction(region) ? nbrText(region).replace("NBR ", "") : "Unavailable"}</td>
                    <td>{region.riskSource?.dataStatus ?? "UNAVAILABLE"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="geo-card">
          <div className="geo-card-header">
            <h3><Flame size={17} /> Hotspot Clusters</h3>
            <span>FIRMS</span>
          </div>
          <div className="cluster-list">
            {liveHotspotClusters.length ? liveHotspotClusters.map((region, index) => (
              <article key={region.id}>
                <b>Cluster {index + 1}</b>
                <span>{region.name}</span>
                <strong>{region.hotspots} hotspots</strong>
                <small>{hasPrediction(region) ? `${region.riskLevel} severity` : "Prediction unavailable"} · {region.hotspotSource?.dataStatus ?? "LIVE"}</small>
              </article>
            )) : (
              <article>
                <b>Unavailable</b>
                <span>No live hotspot clusters</span>
                <strong>FIRMS unavailable</strong>
                <small>Provider data is required before clusters are shown.</small>
              </article>
            )}
          </div>
        </section>

        <section className="geo-card">
          <div className="geo-card-header">
            <h3><Mountain size={17} /> Spatial AI Insights</h3>
            <span>Plain-language</span>
          </div>
          <div className="spatial-insights">
            <p>{selectedRegionInsight}</p>
            <p>{weatherVegetationInsight}</p>
          </div>
        </section>

        <section className="geo-card wide">
          <div className="geo-card-header">
            <h3><Wind size={17} /> Geographic Recommendations</h3>
            <span>Linked to regions</span>
          </div>
          <div className="geo-recommendations">
            {recommendations.map((recommendation, index) => (
              <article key={recommendation}>
                <b>Priority {index + 1}</b>
                <span>{recommendation}</span>
                <small>{rankedRegions[index % rankedRegions.length].name}</small>
              </article>
            ))}
          </div>
        </section>
      </div>
    </motion.section>
  );
}
