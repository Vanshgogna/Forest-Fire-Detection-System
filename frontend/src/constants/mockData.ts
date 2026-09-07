import { AlertItem, RegionRisk, TrendPoint, WeatherSnapshot } from "../types";
import { regionLocations } from "./regionLocations";

export const regions: RegionRisk[] = [
  {
    ...regionLocations.r1,
    riskScore: 91,
    riskLevel: "Critical",
    ndvi: 0.31,
    nbr: 0.18,
    temperature: 29,
    humidity: 18,
    windSpeed: 24,
    rainfall: 0,
    hotspots: 18,
    confidence: 94
  },
  {
    ...regionLocations.r2,
    riskScore: 78,
    riskLevel: "High",
    ndvi: 0.42,
    nbr: 0.31,
    temperature: 36,
    humidity: 26,
    windSpeed: 18,
    rainfall: 1.4,
    hotspots: 11,
    confidence: 88
  },
  {
    ...regionLocations.r3,
    riskScore: 63,
    riskLevel: "Moderate",
    ndvi: 0.49,
    nbr: 0.38,
    temperature: 34,
    humidity: 34,
    windSpeed: 14,
    rainfall: 3.2,
    hotspots: 5,
    confidence: 81
  },
  {
    ...regionLocations.r4,
    riskScore: 29,
    riskLevel: "Low",
    ndvi: 0.71,
    nbr: 0.62,
    temperature: 27,
    humidity: 68,
    windSpeed: 8,
    rainfall: 11.8,
    hotspots: 1,
    confidence: 79
  }
];

export const trendData: TrendPoint[] = [
  { date: "Jun 26", risk: 44, ndvi: 0.62, hotspots: 4, confidence: 78, temperature: 31, humidity: 48 },
  { date: "Jun 27", risk: 51, ndvi: 0.58, hotspots: 6, confidence: 82, temperature: 32, humidity: 43 },
  { date: "Jun 28", risk: 58, ndvi: 0.54, hotspots: 8, confidence: 83, temperature: 34, humidity: 38 },
  { date: "Jun 29", risk: 64, ndvi: 0.5, hotspots: 10, confidence: 86, temperature: 35, humidity: 34 },
  { date: "Jun 30", risk: 72, ndvi: 0.45, hotspots: 13, confidence: 89, temperature: 37, humidity: 29 },
  { date: "Jul 01", risk: 81, ndvi: 0.39, hotspots: 17, confidence: 91, temperature: 38, humidity: 23 },
  { date: "Jul 02", risk: 86, ndvi: 0.36, hotspots: 21, confidence: 93, temperature: 29, humidity: 20 }
];

export const weatherData: WeatherSnapshot[] = [
  { label: "Now", temperature: 29, humidity: 24, wind: 21, rainfall: 0, fireWeatherIndex: 76 },
  { label: "+3h", temperature: 31, humidity: 20, wind: 24, rainfall: 0, fireWeatherIndex: 82 },
  { label: "+6h", temperature: 30, humidity: 22, wind: 19, rainfall: 0.2, fireWeatherIndex: 77 },
  { label: "+9h", temperature: 29, humidity: 33, wind: 13, rainfall: 2.1, fireWeatherIndex: 59 },
  { label: "+12h", temperature: 27, humidity: 45, wind: 9, rainfall: 4.8, fireWeatherIndex: 39 }
];

export const alerts: AlertItem[] = [
  {
    id: "A-2041",
    title: "Critical ignition probability",
    region: "Bandipur Tiger Reserve",
    severity: "Critical",
    confidence: 94,
    status: "New",
    generatedAt: "2026-07-02 11:10",
    explanation: "Very low humidity, dry vegetation, and increasing wind have elevated wildfire probability beyond the response threshold.",
    actions: ["Notify forest control room", "Deploy patrol team", "Verify MODIS hotspot cluster"]
  },
  {
    id: "A-2039",
    title: "Rapid vegetation stress detected",
    region: "Simlipal Biosphere",
    severity: "High",
    confidence: 88,
    status: "Acknowledged",
    generatedAt: "2026-07-02 10:45",
    explanation: "NDVI decline and rising fire weather index indicate fast drying in the eastern buffer zone.",
    actions: ["Inspect watchtower feed", "Prepare local response crew", "Monitor next satellite pass"]
  },
  {
    id: "A-2034",
    title: "Moderate fire weather watch",
    region: "Gir Forest",
    severity: "Moderate",
    confidence: 81,
    status: "Assigned",
    generatedAt: "2026-07-02 09:20",
    explanation: "Warm conditions and scattered hotspots require continued monitoring but do not yet exceed emergency level.",
    actions: ["Keep observation active", "Review rainfall forecast", "Update district bulletin"]
  }
];
