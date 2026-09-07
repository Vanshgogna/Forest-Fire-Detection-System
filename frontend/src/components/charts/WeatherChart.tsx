import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { WeatherSnapshot } from "../../types";

export function WeatherChart({ data }: { data: WeatherSnapshot[] }) {
  if (data.length === 0) {
    return (
      <div className="chart-frame chart-empty-state">
        <strong>Weather forecast unavailable</strong>
        <span>No live or cached Open-Meteo forecast is available for this region.</span>
      </div>
    );
  }

  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ left: -18, right: 10, top: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} />
          <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)" }} />
          <Line type="monotone" dataKey="temperature" stroke="#e53935" strokeWidth={3} />
          <Line type="monotone" dataKey="humidity" stroke="#1976d2" strokeWidth={3} />
          <Line type="monotone" dataKey="fireWeatherIndex" stroke="#fb8c00" strokeWidth={3} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
