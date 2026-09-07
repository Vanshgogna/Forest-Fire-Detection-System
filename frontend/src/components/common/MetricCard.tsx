import { LucideIcon, TrendingDown, TrendingUp } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  trend: "up" | "down" | "flat";
  icon: LucideIcon;
  tone?: "neutral" | "success" | "warning" | "danger";
}

export function MetricCard({ label, value, detail, trend, icon: Icon, tone = "neutral" }: MetricCardProps) {
  const TrendIcon = trend === "down" ? TrendingDown : TrendingUp;
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-icon">
        <Icon size={20} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>
          {trend === "flat" ? null : <TrendIcon size={14} />} {detail}
        </small>
      </div>
    </article>
  );
}
