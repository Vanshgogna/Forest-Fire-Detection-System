import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { mkdtemp, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { build } from "esbuild";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
const React = require("react");
const { renderToString } = require("react-dom/server");
const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
const { MemoryRouter } = require("react-router-dom");

let bundledAppModule;
let testBundleDirectory;

function installBrowserShims() {
  const listener = () => undefined;
  const navigatorValue = { onLine: true, platform: "MacIntel", userAgent: "node-test" };
  const documentValue = {
    documentElement: { dataset: {}, style: {} },
    body: { appendChild: listener, removeChild: listener },
    createElement: () => ({
      style: {},
      children: [],
      appendChild: listener,
      removeChild: listener,
      setAttribute: listener,
      getContext: () => null
    }),
    createElementNS: () => ({
      style: {},
      appendChild: listener,
      removeChild: listener,
      setAttribute: listener
    }),
    addEventListener: listener,
    removeEventListener: listener
  };

  Object.defineProperty(globalThis, "navigator", { value: navigatorValue, configurable: true });
  Object.defineProperty(globalThis, "document", { value: documentValue, configurable: true });
  Object.defineProperty(globalThis, "window", {
    value: {
      addEventListener: listener,
      removeEventListener: listener,
      navigator: navigatorValue,
      document: documentValue,
      matchMedia: () => ({ matches: false, addEventListener: listener, removeEventListener: listener }),
      requestAnimationFrame: (callback) => setTimeout(callback, 0),
      cancelAnimationFrame: (id) => clearTimeout(id),
      setTimeout,
      clearTimeout,
      devicePixelRatio: 1,
      location: { href: "http://localhost/" }
    },
    configurable: true
  });
  globalThis.Element = class Element {};
  globalThis.HTMLElement = class HTMLElement extends globalThis.Element {};
  globalThis.SVGElement = class SVGElement extends globalThis.Element {};
}

async function bundleFrontendModules() {
  const outdir = await mkdtemp(path.join(frontendRoot, ".test-cache-"));
  testBundleDirectory = outdir;
  const outfile = path.join(outdir, "page-smoke-bundle.cjs");
  await build({
    stdin: {
      contents: `
        export { ThemeProvider } from "./src/contexts/ThemeContext.tsx";
        export { EnvironmentalProvider } from "./src/contexts/EnvironmentalContext.tsx";
        export { LandingPage } from "./src/pages/LandingPage.tsx";
        export { DashboardPage } from "./src/pages/DashboardPage.tsx";
        export { MapPage } from "./src/pages/MapPage.tsx";
        export { VegetationPage } from "./src/pages/VegetationPage.tsx";
        export { HotspotsPage } from "./src/pages/HotspotsPage.tsx";
        export { WeatherPage } from "./src/pages/WeatherPage.tsx";
        export { PredictionPage } from "./src/pages/PredictionPage.tsx";
        export { buildExplainabilityReport } from "./src/components/prediction/ExplainabilityDashboard.tsx";
        export { AnalyticsPage } from "./src/pages/AnalyticsPage.tsx";
        export { AlertsPage } from "./src/pages/AlertsPage.tsx";
        export { SettingsPage } from "./src/pages/SettingsPage.tsx";
        export { AboutPage } from "./src/pages/AboutPage.tsx";
        export { NotFoundPage } from "./src/pages/NotFoundPage.tsx";
      `,
      resolveDir: frontendRoot,
      loader: "tsx"
    },
    bundle: true,
    format: "cjs",
    platform: "node",
    external: ["react", "react-dom", "react-dom/server", "@tanstack/react-query", "@tanstack/react-query/*", "react-router-dom", "react-router-dom/*"],
    outfile,
    logLevel: "silent",
    plugins: [
      {
        name: "empty-css",
        setup(pluginBuild) {
          pluginBuild.onLoad({ filter: /\.css$/ }, () => ({ contents: "", loader: "js" }));
        }
      }
    ]
  });
  return require(outfile);
}

function renderPage(exportName, routePath) {
  const Page = bundledAppModule[exportName];
  assert.equal(typeof Page, "function", `${exportName} should be exported`);

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const element = React.createElement(
    QueryClientProvider,
    { client: queryClient },
    React.createElement(
      MemoryRouter,
      { initialEntries: [routePath] },
      React.createElement(
        bundledAppModule.ThemeProvider,
        null,
        React.createElement(bundledAppModule.EnvironmentalProvider, null, React.createElement(Page))
      )
    )
  );

  try {
    return renderToString(element);
  } finally {
    queryClient.clear();
  }
}

const pages = [
  ["LandingPage", "/", "FireSight AI"],
  ["DashboardPage", "/dashboard", "Loading environmental intelligence"],
  ["MapPage", "/map", "Loading GIS layers"],
  ["VegetationPage", "/vegetation", "Vegetation"],
  ["HotspotsPage", "/hotspots", "Hotspot"],
  ["WeatherPage", "/weather", "Weather"],
  ["PredictionPage", "/prediction", "Running prediction model"],
  ["AnalyticsPage", "/analytics", "Analytics"],
  ["AlertsPage", "/alerts", "Loading alert center"],
  ["SettingsPage", "/settings", "Settings"],
  ["AboutPage", "/about", "FireSight"],
  ["NotFoundPage", "/not-found", "not found"]
];

before(async () => {
  installBrowserShims();
  bundledAppModule = await bundleFrontendModules();
});

after(async () => {
  if (testBundleDirectory) {
    await rm(testBundleDirectory, { force: true, recursive: true });
  }
});

describe("React page smoke tests", () => {
  for (const [exportName, routePath, expectedText] of pages) {
    test(`${exportName} renders`, async () => {
      const html = renderPage(exportName, routePath);
      assert.match(html, new RegExp(expectedText, "i"));
    });
  }
});

describe("Explainability export report", () => {
  test("contains selected live region prediction, features, quality, timeline, and provenance", () => {
    const region = {
      id: "r2",
      name: "Simlipal Biosphere",
      state: "Odisha",
      coordinates: [21.6, 86.3],
      riskScore: 35,
      riskLevel: "Low",
      ndvi: 0.632,
      nbr: 0.524,
      temperature: 28,
      humidity: 70,
      windSpeed: 8,
      rainfall: 1.2,
      hotspots: 0,
      confidence: 82,
      riskStatus: "live",
      weatherSource: { status: "live", provider: "open-meteo", sourceType: "weather", dataStatus: "LIVE" },
      vegetationSource: { status: "degraded", provider: "sentinel-2", sourceType: "satellite", dataStatus: "SUSPICIOUS" },
      hotspotSource: { status: "live", provider: "nasa-firms", sourceType: "firms", dataStatus: "RECENT" },
      riskSource: { status: "live", provider: "FireSight prediction API", sourceType: "prediction", dataStatus: "LIVE" },
      prediction: {
        status: "ok",
        region_id: "r2",
        region: "Simlipal Biosphere",
        data_mode: "live",
        risk_score: 35,
        risk_level: "Low",
        confidence: 82,
        model_version: "test-model",
        feature_values: {
          temperature: 28,
          humidity: 70,
          wind_speed: 8,
          rainfall: 1.2,
          ndvi: 0.632,
          nbr: 0.524,
          hotspots: 0,
          fire_weather_index: 12
        },
        explanation: "Backend explanation summary.",
        risk_factors: ["Low rainfall"],
        weather_influence: ["High humidity reduces spread potential"],
        top_contributing_features: [],
        data_quality: { weather: "LIVE", vegetation: "SUSPICIOUS", hotspots: "RECENT" },
        data_provenance: { weather: { provider: "open-meteo" }, vegetation: { provider: "sentinel-2" }, hotspots: { provider: "nasa-firms" } }
      }
    };
    const html = bundledAppModule.buildExplainabilityReport(region, undefined, new Date("2026-08-31T12:00:00Z"), [
      "Environmental snapshot loaded",
      "Existing ML features mapped",
      "FireRiskModelService prediction",
      "Backend explanation returned"
    ]);

    assert.match(html, /Simlipal Biosphere/);
    assert.match(html, /Risk score/);
    assert.match(html, /Risk category/);
    assert.match(html, /Temperature/);
    assert.match(html, /NDVI/);
    assert.match(html, /NBR/);
    assert.match(html, /Hotspots/);
    assert.match(html, /Vegetation status/);
    assert.match(html, /SUSPICIOUS/);
    assert.match(html, /FireRiskModelService prediction/);
    assert.match(html, /Data Provenance/);
    assert.match(html, /nasa-firms/);
  });
});
