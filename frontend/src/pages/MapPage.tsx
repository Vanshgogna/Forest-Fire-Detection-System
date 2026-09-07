import { PageHeader } from "../components/common/PageHeader";
import { GeographicRiskIntelligence } from "../components/maps/GeographicRiskIntelligence";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";

export function MapPage() {
  const { data, isLoading } = useEnvironmentalData();
  const { selectedRegionId } = useEnvironmentalContext();
  if (isLoading || !data) return <div className="loading-state">Loading GIS layers...</div>;
  const selectedRegion = data.regions.find((region) => region.id === selectedRegionId) ?? data.regions[0];
  const weatherAvailable = selectedRegion.weatherSource?.status === "live" || selectedRegion.weatherSource?.status === "degraded";
  const selectedWeatherData = weatherAvailable ? data.weatherDataByRegion?.[selectedRegionId] ?? data.weatherData : [];

  return (
    <>
      <PageHeader
        eyebrow="GIS Analysis"
        title="Geographic Risk Intelligence"
        description="Explore risk polygons, hotspot density, weather overlays, satellite indicators, matrix analysis, and regional response priorities."
      />
      <GeographicRiskIntelligence regions={data.regions} trendData={data.trendData} weatherData={selectedWeatherData} />
    </>
  );
}
