import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RegionRisk } from "../../types";

export function RegionalBarChart({ data }: { data: RegionRisk[] }) {
  const chartData = data.map((region) => ({
    ...region,
    riskScore: region.riskStatus === "unavailable" ? 0 : region.riskScore,
    confidence: region.riskStatus === "unavailable" ? 0 : region.confidence
  }));

  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ left: -18, right: 10, top: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} />
          <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)" }} />
          <Bar dataKey="riskScore" fill="#fb8c00" radius={[8, 8, 0, 0]} />
          <Bar dataKey="confidence" fill="#1976d2" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
