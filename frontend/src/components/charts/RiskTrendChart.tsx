import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { TrendPoint } from "../../types";

export function RiskTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ left: -18, right: 10, top: 10, bottom: 0 }}>
          <defs>
            <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#e53935" stopOpacity={0.28} />
              <stop offset="95%" stopColor="#e53935" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="date" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} />
          <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)" }} />
          <Area type="monotone" dataKey="risk" stroke="#e53935" fill="url(#riskGradient)" strokeWidth={3} />
          <Line type="monotone" dataKey="confidence" stroke="#1976d2" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
