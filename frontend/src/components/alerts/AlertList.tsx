import { AlertTriangle, CheckCircle2, Clock3 } from "lucide-react";
import { AlertItem } from "../../types";
import { getRiskColor } from "../../utils/risk";

function formatAlertTimestamp(timestamp: string) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true
  });
}

export function AlertList({ alerts }: { alerts: AlertItem[] }) {
  return (
    <div className="alert-list">
      {alerts.map((alert) => (
        <article className="alert-card" key={alert.id}>
          <div className="alert-marker" style={{ background: getRiskColor(alert.severity) }}>
            <AlertTriangle size={18} />
          </div>
          <div className="alert-card-main">
            <div className="alert-title-row">
              <h3>{alert.title}</h3>
              <span>{alert.id}</span>
            </div>
            <p>{alert.explanation}</p>
            <div className="alert-meta">
              <span>{alert.region}</span>
              <span>
                <Clock3 size={14} /> {formatAlertTimestamp(alert.generatedAt)}
              </span>
              <span>
                <CheckCircle2 size={14} /> {alert.status}
              </span>
            </div>
          </div>
          <div className="alert-card-summary">
            {typeof alert.riskScore === "number" ? <strong>Risk {alert.riskScore}/100</strong> : null}
            <span>{alert.confidence}% confidence</span>
            <b>{alert.source === "live_prediction" ? "Live Alert" : "Simulation Data"}</b>
            <small>{alert.severity}</small>
          </div>
        </article>
      ))}
    </div>
  );
}
