import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { regions, trendData, weatherData } from "../constants/mockData";
import { EnvironmentalSnapshot, HotspotDetection, LivePredictionResponse, MetricSource, RegionRisk, SentinelSceneStatus, WeatherSnapshot } from "../types";

export const ENVIRONMENTAL_QUERY_KEY = ["environmental-intelligence"] as const;
const ENVIRONMENTAL_STALE_MS = 60_000;
const ENVIRONMENTAL_GC_MS = 300_000;
const MOCK_NETWORK_DELAY_MS = 180;
const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const simulatedWeatherSource: MetricSource = {
  status: "simulated",
  provider: "development fixture",
  sourceType: "simulated_development_fixture",
  dataStatus: "SIMULATED",
  message: "Live weather is unavailable; displayed weather values are development fixtures."
};

const unavailableVegetationSource: MetricSource = {
  status: "unavailable",
  provider: "sentinel-2",
  sourceType: "copernicus_odata_products",
  dataStatus: "UNAVAILABLE",
  message: "Sentinel-2 scene acquisition can run when Copernicus is configured; NDVI data is unavailable until processing completes."
};

const simulatedHotspotSource: MetricSource = {
  status: "simulated",
  provider: "development fixture",
  sourceType: "simulated_development_fixture",
  dataStatus: "SIMULATED",
  message: "Live MODIS/VIIRS hotspot ingestion is not configured."
};

const unavailableHotspotSource: MetricSource = {
  status: "unavailable",
  provider: "nasa-firms",
  sourceType: "firms_area_csv",
  dataStatus: "UNAVAILABLE",
  message: "Hotspot data unavailable. Run FIRMS ingestion with backend credentials to display active-fire detections."
};

const simulatedRiskSource: MetricSource = {
  status: "simulated",
  provider: "development fixture",
  sourceType: "simulated_development_fixture",
  dataStatus: "SIMULATED",
  message: "Risk scores use fixture vegetation and hotspot values until those providers are configured."
};

const unavailableRiskSource: MetricSource = {
  status: "unavailable",
  provider: "FireSight prediction API",
  sourceType: "environmental_snapshot_prediction",
  dataStatus: "UNAVAILABLE",
  message: "Live prediction unavailable until weather, FIRMS hotspots, and Sentinel NDVI are available."
};

const unavailableAlertSource: MetricSource = {
  status: "unavailable",
  provider: "FireSight alert API",
  sourceType: "live_prediction_alert_evaluation",
  dataStatus: "UNAVAILABLE",
  message: "Live alerts unavailable until a valid live prediction can be evaluated."
};

interface WeatherApiResponse {
  status: "ok" | "unavailable";
  data_status?: MetricSource["dataStatus"];
  provider: string;
  source_type: string;
  location: MetricSource["location"];
  current?: {
    temperature: number;
    humidity: number;
    wind_speed: number;
    rainfall: number;
    observed_at: string;
    retrieved_at: string;
    fire_weather_risk_index: number;
  };
  hourly?: Array<{
    time: string;
    temperature_2m?: number;
    relative_humidity_2m?: number;
    wind_speed_10m?: number;
    rain?: number;
    precipitation?: number;
  }>;
  retrieved_at?: string;
  cache?: { status: string; age_seconds: number };
  message?: string;
}

interface HotspotSummaryItem {
  region_id: string;
  available: boolean;
  provider: string;
  product: string;
  source_type: string;
  status: MetricSource["dataStatus"];
  count_24h: number | null;
  count_48h: number | null;
  count_7d: number | null;
  latest_detection_at?: string | null;
  retrieved_at?: string | null;
  detections?: HotspotDetection[];
  message?: string | null;
  attribution?: string | null;
}

interface HotspotApiResponse {
  hotspots: HotspotSummaryItem[];
  total: number | null;
  status: MetricSource["dataStatus"];
  provider: string;
  source_type: string;
  message?: string;
}

interface SentinelStatusApiResponse {
  scenes: SentinelSceneStatus[];
  total: number;
  available: number;
  status: MetricSource["dataStatus"];
  provider: string;
  source_type: string;
  message?: string;
}

function riskStatusFromPrediction(response?: LivePredictionResponse): RegionRisk["riskStatus"] {
  if (!response) return "unavailable";
  if (response.status !== "ok") return "unavailable";
  return response.data_mode === "simulation" ? "simulation" : "live";
}

function sourceFromPrediction(response?: LivePredictionResponse): MetricSource {
  if (!response) return unavailableRiskSource;
  if (response.status !== "ok") {
    return {
      ...unavailableRiskSource,
      message: response.message ?? unavailableRiskSource.message,
      dataStatus: "UNAVAILABLE"
    };
  }
  const isSimulation = response.data_mode === "simulation";
  return {
    status: isSimulation ? "simulated" : "live",
    provider: "FireSight prediction API",
    sourceType: "environmental_snapshot_prediction",
    dataStatus: isSimulation ? "SIMULATED" : "LIVE",
    message: isSimulation
      ? "Simulation prediction from existing fixture behavior."
      : `${response.risk_level ?? "Risk"} prediction from canonical environmental snapshot.`
  };
}

function updatedMinutesAgo(retrievedAt?: string) {
  if (!retrievedAt) return "source timestamp unavailable";
  const ageMs = Date.now() - new Date(retrievedAt).getTime();
  if (!Number.isFinite(ageMs) || ageMs < 0) return "updated just now";
  const minutes = Math.max(0, Math.round(ageMs / 60_000));
  return minutes <= 1 ? "updated just now" : `updated ${minutes} min ago`;
}

function sourceFromWeather(response: WeatherApiResponse): MetricSource {
  if (response.status !== "ok" || !response.current) {
    return {
      status: "unavailable",
      provider: response.provider ?? "Open-Meteo",
      sourceType: response.source_type ?? "forecast_model_current_conditions",
      location: response.location,
      dataStatus: response.data_status ?? "UNAVAILABLE",
      message: response.message ?? "Live weather temporarily unavailable"
    };
  }
  const dataStatus = response.data_status ?? (response.cache?.status === "hit" ? "CACHED" : "LIVE");
  return {
    status: dataStatus === "LIVE" ? "live" : dataStatus === "UNAVAILABLE" ? "unavailable" : "degraded",
    provider: response.provider,
    sourceType: response.source_type,
    observedAt: response.current.observed_at,
    retrievedAt: response.retrieved_at,
    cacheStatus: response.cache?.status,
    dataStatus,
    location: response.location,
    message: `${dataStatus} · ${updatedMinutesAgo(response.retrieved_at)}`
  };
}

function sourceFromHotspots(summary?: HotspotSummaryItem, response?: HotspotApiResponse): MetricSource {
  if (!summary?.available) {
    return {
      ...unavailableHotspotSource,
      dataStatus: summary?.status ?? response?.status ?? "UNAVAILABLE",
      message: summary?.message ?? response?.message ?? unavailableHotspotSource.message
    };
  }
  return {
    status: "live",
    provider: summary.provider,
    sourceType: summary.source_type,
    observedAt: summary.latest_detection_at ?? undefined,
    retrievedAt: summary.retrieved_at ?? undefined,
    dataStatus: summary.status,
    message: `${summary.status} · ${summary.count_24h ?? 0} FIRMS active-fire detections in 24h`
  };
}

function sourceFromSentinel(scene?: SentinelSceneStatus, response?: SentinelStatusApiResponse): MetricSource {
  if (!scene?.available) {
    return {
      ...unavailableVegetationSource,
      dataStatus: scene?.status ?? response?.status ?? "UNAVAILABLE",
      message: scene?.message ?? response?.message ?? unavailableVegetationSource.message
    };
  }
  const ndvi = scene.ndvi_processing;
  if ((ndvi?.status === "READY" || ndvi?.status === "LOW_QUALITY") && typeof ndvi.mean === "number") {
    const dataStatus = ndvi.quality_status ?? scene.status ?? "LIVE";
    return {
      status: dataStatus === "SUSPICIOUS" ? "degraded" : "live",
      provider: scene.provider,
      sourceType: "sentinel2_l2a_ndvi_processing",
      observedAt: scene.captured_at ?? undefined,
      retrievedAt: ndvi.processed_at ?? scene.retrieved_at ?? undefined,
      dataStatus,
      message: `${dataStatus} · NDVI ${ndvi.mean.toFixed(3)} · ${Math.round(ndvi.valid_pixel_percentage ?? 0)}% valid pixels`
    };
  }
  return {
    status: "unavailable",
    provider: scene.provider,
    sourceType: scene.source_type,
    observedAt: scene.captured_at ?? undefined,
    retrievedAt: scene.retrieved_at ?? undefined,
    dataStatus: "UNAVAILABLE",
    message: `Scene acquired: ${scene.product_level ?? "Sentinel-2"} · NDVI data unavailable until processing.`
  };
}

function forecastFromWeather(response: WeatherApiResponse): WeatherSnapshot[] {
  const hourly = response.hourly?.slice(0, 12) ?? [];
  if (response.status !== "ok" || hourly.length === 0) return [];
  return hourly.map((item) => ({
    label: new Date(item.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    temperature: Math.round(item.temperature_2m ?? 0),
    humidity: Math.round(item.relative_humidity_2m ?? 0),
    wind: Math.round(item.wind_speed_10m ?? 0),
    rainfall: item.rain ?? item.precipitation ?? 0,
    fireWeatherIndex: Math.round(((item.temperature_2m ?? 0) * 0.8 + (100 - (item.relative_humidity_2m ?? 100)) * 0.6 + (item.wind_speed_10m ?? 0) * 0.7) / 2),
    observedAt: item.time,
    provider: response.provider,
    sourceType: response.source_type
  }));
}

async function loadLiveWeather(): Promise<{ regions: RegionRisk[]; weatherData: WeatherSnapshot[]; weatherDataByRegion: Record<string, WeatherSnapshot[]>; source: MetricSource }> {
  const responses = await Promise.allSettled(
    regions.map((region) => api.get<WeatherApiResponse>("/weather/", { params: { region_id: region.id, forecast_days: 3 } }))
  );
  const weatherByRegion = new Map<string, WeatherApiResponse>();
  for (const result of responses) {
    if (result.status === "fulfilled") {
      const response = result.value.data;
      if (response.location?.region) {
        weatherByRegion.set(response.location.region, response);
      }
    }
  }

  const updatedRegions = regions.map((region) => {
    const weather = weatherByRegion.get(region.name);
    const source = weather ? sourceFromWeather(weather) : simulatedWeatherSource;
    if (weather?.status === "ok" && weather.current) {
      return {
        ...region,
        temperature: Math.round(weather.current.temperature),
        humidity: Math.round(weather.current.humidity),
        windSpeed: Math.round(weather.current.wind_speed),
        rainfall: weather.current.rainfall,
        weatherSource: source,
        vegetationSource: unavailableVegetationSource,
        hotspotSource: simulatedHotspotSource
      };
    }
    return { ...region, weatherSource: source, vegetationSource: unavailableVegetationSource, hotspotSource: simulatedHotspotSource };
  });

  const primaryWeather = weatherByRegion.get(regions[0].name);
  const weatherDataByRegion = Object.fromEntries(
    regions.map((region) => {
      const weather = weatherByRegion.get(region.name);
      return [region.id, weather ? forecastFromWeather(weather) : []];
    })
  );
  return {
    regions: updatedRegions,
    weatherData: primaryWeather ? forecastFromWeather(primaryWeather) : [],
    weatherDataByRegion,
    source: primaryWeather ? sourceFromWeather(primaryWeather) : simulatedWeatherSource
  };
}

async function loadLiveHotspots(): Promise<{ byRegion: Map<string, HotspotSummaryItem>; source: MetricSource }> {
  try {
    const response = await api.get<HotspotApiResponse>("/hotspots/");
    const byRegion = new Map<string, HotspotSummaryItem>();
    response.data.hotspots.forEach((item) => byRegion.set(item.region_id, item));
    const firstAvailable = response.data.hotspots.find((item) => item.available);
    return {
      byRegion,
      source: sourceFromHotspots(firstAvailable ?? response.data.hotspots[0], response.data)
    };
  } catch {
    return {
      byRegion: new Map<string, HotspotSummaryItem>(),
      source: unavailableHotspotSource
    };
  }
}

async function loadLiveSentinelScenes(): Promise<{ byRegion: Map<string, SentinelSceneStatus>; source: MetricSource }> {
  try {
    const response = await api.get<SentinelStatusApiResponse>("/vegetation/satellite/status");
    const byRegion = new Map<string, SentinelSceneStatus>();
    response.data.scenes.forEach((item) => byRegion.set(item.region_id, item));
    const firstAvailable = response.data.scenes.find((item) => item.available);
    return {
      byRegion,
      source: sourceFromSentinel(firstAvailable ?? response.data.scenes[0], response.data)
    };
  } catch {
    return {
      byRegion: new Map<string, SentinelSceneStatus>(),
      source: unavailableVegetationSource
    };
  }
}

async function loadLivePredictions(): Promise<{ byRegion: Map<string, LivePredictionResponse>; source: MetricSource }> {
  const responses = await Promise.allSettled(regions.map((region) => api.get<LivePredictionResponse>(`/prediction/${region.id}`)));
  const byRegion = new Map<string, LivePredictionResponse>();
  for (const result of responses) {
    if (result.status === "fulfilled") {
      const prediction = result.value.data;
      byRegion.set(prediction.region_id, prediction);
    }
  }
  const firstPrediction = [...byRegion.values()].find((prediction) => prediction.status === "ok") ?? [...byRegion.values()][0];
  return {
    byRegion,
    source: sourceFromPrediction(firstPrediction)
  };
}

export function useEnvironmentalData() {
  return useQuery({
    queryKey: ENVIRONMENTAL_QUERY_KEY,
    queryFn: async () => {
      await wait(MOCK_NETWORK_DELAY_MS);
      try {
        const liveWeather = await loadLiveWeather();
        const [liveHotspots, liveSentinel, livePredictions] = await Promise.all([loadLiveHotspots(), loadLiveSentinelScenes(), loadLivePredictions()]);
        const regionsWithHotspots = liveWeather.regions.map((region) => {
          const hotspotSummary = liveHotspots.byRegion.get(region.id);
          const sentinelScene = liveSentinel.byRegion.get(region.id);
          const prediction = livePredictions.byRegion.get(region.id);
          const hotspotSource = sourceFromHotspots(hotspotSummary, { hotspots: [], total: null, status: "UNAVAILABLE", provider: "nasa-firms", source_type: "firms_area_csv" });
          const predictionSource = sourceFromPrediction(prediction);
          const featureValues = prediction?.status === "ok" ? prediction.feature_values : undefined;
          return {
            ...region,
            riskScore: prediction?.status === "ok" && typeof prediction.risk_score === "number" ? prediction.risk_score : region.riskScore,
            riskLevel: prediction?.status === "ok" && prediction.risk_level ? prediction.risk_level : region.riskLevel,
            confidence: prediction?.status === "ok" && typeof prediction.confidence === "number" ? prediction.confidence : region.confidence,
            temperature: typeof featureValues?.temperature === "number" ? Math.round(featureValues.temperature) : region.temperature,
            humidity: typeof featureValues?.humidity === "number" ? Math.round(featureValues.humidity) : region.humidity,
            windSpeed: typeof featureValues?.wind_speed === "number" ? Math.round(featureValues.wind_speed) : region.windSpeed,
            rainfall: typeof featureValues?.rainfall === "number" ? featureValues.rainfall : region.rainfall,
            ndvi: typeof featureValues?.ndvi === "number" ? featureValues.ndvi : region.ndvi,
            nbr: typeof featureValues?.nbr === "number" ? featureValues.nbr : region.nbr,
            hotspots: prediction?.status === "ok" && typeof featureValues?.hotspots === "number" ? featureValues.hotspots : hotspotSummary?.available ? hotspotSummary.count_24h ?? 0 : region.hotspots,
            hotspotDetections: hotspotSummary?.detections ?? [],
            hotspotSource,
            sentinelScene,
            vegetationSource: sourceFromSentinel(sentinelScene, { scenes: [], total: 0, available: 0, status: "UNAVAILABLE", provider: "sentinel-2", source_type: "copernicus_odata_products" }),
            riskStatus: riskStatusFromPrediction(prediction),
            riskSource: predictionSource,
            prediction
          };
        });
        return {
          regions: regionsWithHotspots,
          trendData,
          weatherData: liveWeather.weatherData,
          weatherDataByRegion: liveWeather.weatherDataByRegion,
          alerts: [] as EnvironmentalSnapshot["alerts"],
          provenance: {
            weather: liveWeather.source,
            vegetation: liveSentinel.source,
            hotspots: liveHotspots.source,
            risk: livePredictions.source,
            alerts: unavailableAlertSource
          }
        } satisfies EnvironmentalSnapshot;
      } catch {
        return {
          regions: regions.map((region) => ({
            ...region,
            weatherSource: simulatedWeatherSource,
            vegetationSource: unavailableVegetationSource,
            hotspotSource: unavailableHotspotSource,
            hotspotDetections: [],
            riskStatus: "unavailable",
            riskSource: unavailableRiskSource
          })),
          trendData,
          weatherData,
          weatherDataByRegion: Object.fromEntries(regions.map((region) => [region.id, weatherData])),
          alerts: [] as EnvironmentalSnapshot["alerts"],
          provenance: {
            weather: simulatedWeatherSource,
            vegetation: unavailableVegetationSource,
            hotspots: unavailableHotspotSource,
            risk: unavailableRiskSource,
            alerts: unavailableAlertSource
          }
        } satisfies EnvironmentalSnapshot;
      }
    },
    staleTime: ENVIRONMENTAL_STALE_MS,
    gcTime: ENVIRONMENTAL_GC_MS,
    refetchOnMount: false,
    refetchOnWindowFocus: false
  });
}
