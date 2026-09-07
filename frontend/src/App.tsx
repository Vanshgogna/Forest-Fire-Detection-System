import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { LoadingFallback } from "./components/common/LoadingFallback";
import { OfflineStatus } from "./components/common/OfflineStatus";
import { ThemeProvider } from "./contexts/ThemeContext";
import { EnvironmentalProvider } from "./contexts/EnvironmentalContext";
import { DashboardLayout } from "./layouts/DashboardLayout";

const LandingPage = lazy(() => import("./pages/LandingPage").then((module) => ({ default: module.LandingPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const MapPage = lazy(() => import("./pages/MapPage").then((module) => ({ default: module.MapPage })));
const VegetationPage = lazy(() => import("./pages/VegetationPage").then((module) => ({ default: module.VegetationPage })));
const HotspotsPage = lazy(() => import("./pages/HotspotsPage").then((module) => ({ default: module.HotspotsPage })));
const WeatherPage = lazy(() => import("./pages/WeatherPage").then((module) => ({ default: module.WeatherPage })));
const PredictionPage = lazy(() => import("./pages/PredictionPage").then((module) => ({ default: module.PredictionPage })));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const AlertsPage = lazy(() => import("./pages/AlertsPage").then((module) => ({ default: module.AlertsPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const AboutPage = lazy(() => import("./pages/AboutPage").then((module) => ({ default: module.AboutPage })));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage").then((module) => ({ default: module.NotFoundPage })));

export default function App() {
  return (
    <ThemeProvider>
      <EnvironmentalProvider>
        <ErrorBoundary>
          <OfflineStatus />
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route element={<DashboardLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/vegetation" element={<VegetationPage />} />
                <Route path="/hotspots" element={<HotspotsPage />} />
                <Route path="/weather" element={<WeatherPage />} />
                <Route path="/prediction" element={<PredictionPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/about" element={<AboutPage />} />
              </Route>
              <Route path="/not-found" element={<NotFoundPage />} />
              <Route path="*" element={<Navigate to="/not-found" replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </EnvironmentalProvider>
    </ThemeProvider>
  );
}
