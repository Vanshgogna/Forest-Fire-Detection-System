import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CloudSun,
  Flame,
  Map,
  Satellite,
  ShieldCheck,
  Sparkles,
  ThermometerSun
} from "lucide-react";
import { Link } from "react-router-dom";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { RegionRisk } from "../types";

function sourceLabel(source?: RegionRisk["weatherSource"]) {
  if (!source) return "UNAVAILABLE";
  return source.dataStatus ?? source.status.toUpperCase();
}

function formatMetric(value: number | undefined, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";
}

function previewCopy(region?: RegionRisk) {
  if (!region) {
    return {
      name: "Data unavailable",
      risk: "--",
      category: "Waiting for live prediction",
      confidence: "Unavailable",
      ndvi: "--",
      nbr: "--",
      hotspots: "--",
      weather: "UNAVAILABLE",
      vegetation: "UNAVAILABLE",
      hotspot: "UNAVAILABLE",
      message: "Live environmental intelligence will appear here when the backend data pipeline is available."
    };
  }

  const hasPrediction = region.riskStatus === "live" && region.prediction?.data_mode !== "simulation";
  return {
    name: region.name,
    risk: hasPrediction ? String(region.riskScore) : "--",
    category: hasPrediction ? `${region.riskLevel} risk` : "Prediction unavailable",
    confidence: hasPrediction ? `${region.confidence}% confidence` : "Unavailable",
    ndvi: region.vegetationSource?.status === "live" || region.vegetationSource?.status === "degraded" ? formatMetric(region.ndvi, 3) : "--",
    nbr: hasPrediction ? formatMetric(region.nbr, 3) : "--",
    hotspots: region.hotspotSource?.status === "live" || region.hotspotSource?.status === "degraded" ? String(region.hotspots) : "--",
    weather: sourceLabel(region.weatherSource),
    vegetation: sourceLabel(region.vegetationSource),
    hotspot: sourceLabel(region.hotspotSource),
    message: region.riskSource?.message ?? "Live prediction status unavailable."
  };
}

const workflow = [
  {
    title: "Weather Intelligence",
    text: "Real-time temperature, humidity, rainfall, and wind signals.",
    icon: CloudSun
  },
  {
    title: "Satellite Monitoring",
    text: "Sentinel-2 vegetation indicators using NDVI and NBR.",
    icon: Satellite
  },
  {
    title: "Hotspot Detection",
    text: "NASA FIRMS thermal hotspot intelligence.",
    icon: Flame
  },
  {
    title: "AI Risk Prediction",
    text: "Machine learning combines environmental signals into fire risk intelligence.",
    icon: BrainCircuit
  }
];

const capabilities = [
  ["Sentinel-2 Intelligence", "Real NDVI and NBR vegetation indicators.", Satellite],
  ["FIRMS Hotspot Monitoring", "Real thermal hotspot detection.", Flame],
  ["Weather Intelligence", "Environmental conditions for fire risk analysis.", ThermometerSun],
  ["AI Risk Prediction", "Machine learning-based wildfire risk scoring.", BrainCircuit],
  ["Geographic Risk Intelligence", "Regional monitoring and risk visualization.", Map],
  ["Alert Intelligence", "Risk threshold monitoring and alerts.", AlertTriangle]
] as const;

export function LandingPage() {
  const { data, isLoading } = useEnvironmentalData();
  const previewRegion = data?.regions[0];
  const preview = previewCopy(previewRegion);
  const previewUnavailable = !previewRegion || previewRegion.riskStatus !== "live" || previewRegion.prediction?.data_mode === "simulation";

  return (
    <div className="landing">
      <header className="landing-nav">
        <Link to="/" className="brand landing-brand" aria-label="FireSight AI home">
          <span className="brand-logo" aria-hidden="true">
            <img src="/favicon.svg" alt="" />
          </span>
          <div>
            <strong>FireSight AI</strong>
            <small>Forest Risk Intelligence</small>
          </div>
        </Link>
        <nav className="landing-nav-links" aria-label="Landing page sections">
          <a href="#platform">Platform</a>
          <a href="#intelligence">Intelligence</a>
          <a href="#how-it-works">How It Works</a>
        </nav>
        <Link className="button primary landing-nav-cta" to="/dashboard">
          Open Dashboard <ArrowRight size={16} />
        </Link>
      </header>

      <main>
        <section className="hero" id="platform">
          <div className="hero-background" aria-hidden="true" />
          <div className="hero-copy">
            <span className="live-badge"><i /> {previewUnavailable ? "Platform Preview" : "Live Environmental Intelligence"}</span>
            <h1>
              AI-Powered <span>Forest Fire</span> Intelligence
            </h1>
            <p>
              Detect wildfire risk earlier using real-time weather intelligence, Sentinel-2 satellite imagery,
              vegetation indicators, FIRMS hotspots, and machine learning.
            </p>
            <div className="hero-actions">
              <Link className="button primary" to="/dashboard">
                Open Dashboard <ArrowRight size={18} />
              </Link>
              <a className="button secondary landing-secondary" href="#how-it-works">
                Explore How It Works
              </a>
            </div>
            <div className="data-strip" aria-label="Connected data sources">
              <span><ShieldCheck size={15} /> Sentinel-2 Satellite Data</span>
              <span><ShieldCheck size={15} /> NASA FIRMS Hotspots</span>
              <span><ShieldCheck size={15} /> Live Weather Intelligence</span>
            </div>
          </div>

          <aside className="live-preview" aria-label="Live risk intelligence preview">
            <div className="preview-topline">
              <span>{isLoading ? "Loading Intelligence" : previewUnavailable ? "Platform Preview" : "Live Risk Intelligence"}</span>
              <strong className={previewUnavailable ? "preview-status unavailable" : "preview-status"}><i /> {previewUnavailable ? "Unavailable" : "Live"}</strong>
            </div>
            <div className="preview-region">
              <span>{isLoading ? "Loading live region" : preview.name}</span>
              <small>{preview.message}</small>
            </div>
            <div className="preview-risk">
              <strong>{isLoading ? "--" : preview.risk}</strong>
              <span>{isLoading ? "Loading prediction" : preview.category}</span>
              <small>{isLoading ? "Connecting to backend intelligence" : preview.confidence}</small>
            </div>
            <div className="preview-metrics">
              <article>
                <span>NDVI</span>
                <strong>{isLoading ? "--" : preview.ndvi}</strong>
              </article>
              <article>
                <span>NBR</span>
                <strong>{isLoading ? "--" : preview.nbr}</strong>
              </article>
              <article>
                <span>Hotspots</span>
                <strong>{isLoading ? "--" : preview.hotspots}</strong>
              </article>
            </div>
            <div className="preview-sources">
              <span>Weather <strong>{isLoading ? "LOADING" : preview.weather}</strong></span>
              <span>Sentinel-2 <strong>{isLoading ? "LOADING" : preview.vegetation}</strong></span>
              <span>FIRMS <strong>{isLoading ? "LOADING" : preview.hotspot}</strong></span>
            </div>
          </aside>
        </section>

        <section className="landing-section process-section" id="how-it-works">
          <div className="section-heading">
            <span className="eyebrow">How FireSight Works</span>
            <h2>From Environmental Data to Actionable Intelligence</h2>
          </div>
          <div className="process-grid">
            {workflow.map((item, index) => (
              <article key={item.title}>
                <div>
                  <b>{String(index + 1).padStart(2, "0")}</b>
                  <item.icon size={20} />
                </div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section capabilities-section" id="intelligence">
          <div className="section-heading">
            <span className="eyebrow">Operational Capabilities</span>
            <h2>Operational Intelligence Modules</h2>
          </div>
          <div className="capability-grid">
            {capabilities.map(([title, text, Icon]) => (
              <article key={title}>
                <Icon size={22} />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-final-cta">
          <div>
            <Sparkles size={24} />
            <h2>Ready to Explore Fire Risk Intelligence?</h2>
            <p>Open the FireSight platform to inspect live environmental conditions, satellite vegetation, hotspot activity, predictions, and alerts.</p>
          </div>
          <Link className="button primary" to="/dashboard">
            Open FireSight Dashboard <ArrowRight size={18} />
          </Link>
        </section>
      </main>
    </div>
  );
}
