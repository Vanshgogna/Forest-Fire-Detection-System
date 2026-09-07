import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Bell, Radio, RefreshCw } from "lucide-react";
import { AlertList } from "../components/alerts/AlertList";
import { PageHeader } from "../components/common/PageHeader";
import { Panel } from "../components/common/Panel";
import { useEnvironmentalContext } from "../contexts/EnvironmentalContext";
import { useEnvironmentalData } from "../hooks/useEnvironmentalData";
import { api } from "../services/api";
import { AlertItem } from "../types";

interface AlertApiItem {
  id: string;
  title: string;
  region: string;
  severity: AlertItem["severity"];
  confidence: number;
  status: AlertItem["status"];
  generated_at: string;
  explanation: string;
  actions: string[];
  source?: AlertItem["source"];
  data_mode?: string;
  risk_score?: number;
  risk_level?: AlertItem["riskLevel"];
}

interface LiveAlertEvaluationResponse {
  status: "ok" | "unavailable";
  region_id: string;
  region?: string;
  prediction_status?: string;
  message?: string;
  alerts: AlertApiItem[];
  source: "live_prediction";
}

function alertFromApi(alert: AlertApiItem): AlertItem {
  return {
    id: alert.id,
    title: alert.title,
    region: alert.region,
    severity: alert.severity,
    confidence: alert.confidence,
    status: alert.status,
    generatedAt: alert.generated_at,
    explanation: alert.explanation,
    actions: alert.actions,
    source: alert.source ?? "live_prediction",
    dataMode: alert.data_mode,
    riskScore: alert.risk_score,
    riskLevel: alert.risk_level
  };
}

export function AlertsPage() {
  const { selectedRegionId } = useEnvironmentalContext();
  const { data, isLoading } = useEnvironmentalData();
  const selectedRegion = data?.regions.find((region) => region.id === selectedRegionId) ?? data?.regions[0];
  const alertsQuery = useQuery({
    queryKey: ["region-alert-evaluation", selectedRegionId],
    queryFn: async ({ signal }) => {
      const response = await api.get<LiveAlertEvaluationResponse>(`/alerts/evaluate/${selectedRegionId}`, { signal });
      return response.data;
    },
    enabled: Boolean(selectedRegionId),
    staleTime: 30_000,
    gcTime: 120_000,
    refetchOnWindowFocus: false
  });

  if (isLoading || !data) return <div className="loading-state">Loading alert center...</div>;
  const alertEvaluation = alertsQuery.data;
  const selectedAlerts = alertEvaluation?.alerts.map(alertFromApi).filter((alert) => alert.region === selectedRegion?.name) ?? [];
  const isAlertLoading = alertsQuery.isPending || alertsQuery.isFetching;
  const alertError = alertsQuery.error as { userMessage?: string; message?: string } | null;
  const liveAlertAvailable = alertEvaluation?.status === "ok";
  const evaluationUnavailable = alertEvaluation?.status === "unavailable";
  const alertMessage = alertEvaluation?.message ?? "Live alert evaluation is loading for the selected region.";
  const predictionMessage = selectedRegion?.riskSource?.message ?? data.provenance.risk.message ?? "Live prediction unavailable";
  const regionName = selectedRegion?.name ?? "Selected region";

  return (
    <>
      <PageHeader
        eyebrow={`Alert Center · ${regionName}`}
        title="Operational Early Warnings"
        description={liveAlertAvailable ? `Live AlertEngine evaluation for ${regionName}.` : predictionMessage}
        actions={<span className="live-chip"><Bell size={15} /> Region: {regionName}</span>}
      />
      <Panel title="Alert Stream" subtitle={`Region-specific live alerts for ${regionName}`}>
        <div className="alert-toolbar">
          <div className="live-chip">
            {isAlertLoading ? <RefreshCw size={14} /> : <Radio size={14} />}
            Alerts: live prediction · Evaluation: {isAlertLoading ? "loading" : liveAlertAvailable ? "available" : "unavailable"}
          </div>
          {evaluationUnavailable ? <div className="live-chip warning-chip"><AlertCircle size={14} /> {alertMessage}</div> : null}
        </div>
        {isAlertLoading ? (
          <div className="alert-loading-state">Loading live alerts for {regionName}...</div>
        ) : alertError ? (
          <div className="alert-empty-state error-state-inline">Alert evaluation failed: {alertError.userMessage ?? alertError.message ?? "Backend request failed."}</div>
        ) : evaluationUnavailable ? (
          <div className="alert-empty-state">{alertMessage}</div>
        ) : selectedAlerts.length > 0 ? (
          <AlertList alerts={selectedAlerts} />
        ) : (
          <div className="alert-empty-state">No active alerts for this region</div>
        )}
      </Panel>
    </>
  );
}
