export type RiskLevel = "Low" | "Moderate" | "High" | "Critical";

export interface RegionRisk {
  id: string;
  name: string;
  state: string;
  coordinates: [number, number];
  riskScore: number;
  riskLevel: RiskLevel;
  ndvi: number;
  nbr: number;
  temperature: number;
  humidity: number;
  windSpeed: number;
  rainfall: number;
  hotspots: number;
  confidence: number;
  hotspotDetections?: HotspotDetection[];
  weatherSource?: MetricSource;
  vegetationSource?: MetricSource;
  hotspotSource?: MetricSource;
  sentinelScene?: SentinelSceneStatus;
  riskStatus?: "live" | "simulation" | "unavailable" | "loading" | "error";
  riskSource?: MetricSource;
  prediction?: LivePredictionResponse;
}

export interface SentinelSceneStatus {
  region_id: string;
  available: boolean;
  provider: string;
  source_type: string;
  status: MetricSource["dataStatus"];
  acquisition_status: string;
  product_id?: string | null;
  scene_id?: string | null;
  platform?: string | null;
  product_level?: string | null;
  captured_at?: string | null;
  retrieved_at?: string | null;
  cloud_percentage?: number | null;
  tile_id?: string | null;
  storage_available: boolean;
  file_size_bytes?: number | null;
  checksum?: string | null;
  raster_processing?: {
    status: string;
    available_bands: string[];
    analysis_crs?: string | null;
    resolution?: [number, number] | null;
    processing_time?: string | null;
  };
  quality_masking?: {
    status: string;
    quality_status?: MetricSource["dataStatus"] | null;
    masking_version?: string | null;
    valid_pixel_percentage?: number | null;
    masked_pixel_percentage?: number | null;
    cloud_percentage?: number | null;
    shadow_percentage?: number | null;
    cirrus_percentage?: number | null;
    snow_percentage?: number | null;
    processed_at?: string | null;
  };
  ndvi_processing?: {
    status: string;
    quality_status?: MetricSource["dataStatus"] | null;
    processing_version?: string | null;
    mean?: number | null;
    median?: number | null;
    min?: number | null;
    max?: number | null;
    valid_pixel_percentage?: number | null;
    processed_at?: string | null;
  };
  message?: string | null;
  attribution?: string | null;
}

export interface HotspotDetection {
  id?: number | null;
  latitude: number;
  longitude: number;
  detected_at: string;
  retrieved_at?: string | null;
  satellite?: string | null;
  instrument?: string | null;
  confidence: number;
  severity: RiskLevel;
  frp?: number | null;
  brightness?: number | null;
  source_record_id?: string | null;
}

export interface WeatherSnapshot {
  label: string;
  temperature: number;
  humidity: number;
  wind: number;
  rainfall: number;
  fireWeatherIndex: number;
  observedAt?: string;
  provider?: string;
  sourceType?: string;
}

export interface TrendPoint {
  date: string;
  risk: number;
  ndvi: number;
  hotspots: number;
  confidence: number;
  temperature: number;
  humidity: number;
}

export interface FeatureContribution {
  feature: string;
  display_name: string;
  value: number;
  importance: number;
  contribution: number;
  direction: "increases_risk" | "reduces_risk";
  influence_group: "weather" | "vegetation" | "historical" | "model";
  explanation: string;
}

export interface PredictionExplanation {
  prediction: RiskLevel;
  confidence_score: number;
  summary: string;
  why: string;
  top_contributing_features: FeatureContribution[];
  feature_importance: Record<string, number>;
  risk_factors: string[];
  weather_influence: string[];
  vegetation_influence: string[];
  historical_trend_influence: string[];
  historical_comparison: Record<string, unknown>;
  confidence_explanation: string;
  recommendation_rationales: Array<{ recommendation: string; rationale: string }>;
  visual_explanations: Record<string, unknown>;
  interpretability: Record<string, unknown>;
}

export interface PredictionResponse {
  region: string;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: number;
  input_snapshot?: Record<string, unknown>;
  explanation: string;
  explanation_details: PredictionExplanation;
  top_contributing_features: FeatureContribution[];
  feature_importance: Record<string, number>;
  risk_factors: string[];
  historical_comparison: Record<string, unknown>;
  weather_influence: string[];
  vegetation_influence: string[];
  historical_trend_influence: string[];
  confidence_explanation: string;
  visual_explanations: Record<string, unknown>;
  interpretability: Record<string, unknown>;
  recommendation_rationales: Array<{ recommendation: string; rationale: string }>;
  recommendations: string[];
}

export interface LivePredictionResponse {
  status: "ok" | "unavailable";
  region_id: string;
  region: string;
  data_mode: "live" | "simulation" | string;
  message?: string;
  risk_score?: number;
  risk_level?: RiskLevel;
  confidence?: number;
  model_version?: string;
  feature_schema?: string[];
  feature_values?: Record<string, number>;
  defaulted_features?: string[];
  input_snapshot?: Record<string, unknown>;
  explanation?: string;
  explanation_details?: PredictionExplanation;
  top_contributing_features?: FeatureContribution[];
  feature_importance?: Record<string, number>;
  risk_factors?: string[];
  historical_comparison?: Record<string, unknown>;
  weather_influence?: string[];
  vegetation_influence?: string[];
  historical_trend_influence?: string[];
  confidence_explanation?: string;
  visual_explanations?: Record<string, unknown>;
  interpretability?: Record<string, unknown>;
  recommendation_rationales?: Array<{ recommendation: string; rationale: string }>;
  recommendations?: string[];
  missing_sources?: Array<{ source: string; status: string; reason: string }>;
  availability?: Record<string, boolean>;
  data_quality?: Record<string, string>;
  data_provenance?: Record<string, Record<string, unknown> | null>;
}

export interface AlertItem {
  id: string;
  title: string;
  region: string;
  severity: RiskLevel;
  confidence: number;
  status: "New" | "Acknowledged" | "Assigned" | "Resolved";
  generatedAt: string;
  explanation: string;
  actions: string[];
  source?: "live_prediction" | "simulation";
  dataMode?: string;
  riskScore?: number;
  riskLevel?: RiskLevel;
}

export interface MetricSource {
  status: "live" | "degraded" | "simulated" | "unavailable";
  provider: string;
  sourceType: string;
  observedAt?: string;
  retrievedAt?: string;
  cacheStatus?: string;
  dataStatus?: "LIVE" | "RECENT" | "CACHED" | "STALE" | "UNAVAILABLE" | "SUSPICIOUS" | "SIMULATED";
  location?: {
    region: string;
    latitude: number;
    longitude: number;
    timezone: string;
    coordinate_method?: string;
  };
  message?: string;
}

export interface EnvironmentalSnapshot {
  regions: RegionRisk[];
  trendData: TrendPoint[];
  weatherData: WeatherSnapshot[];
  weatherDataByRegion?: Record<string, WeatherSnapshot[]>;
  alerts: AlertItem[];
  provenance: {
    weather: MetricSource;
    vegetation: MetricSource;
    hotspots: MetricSource;
    risk: MetricSource;
    alerts: MetricSource;
  };
}
