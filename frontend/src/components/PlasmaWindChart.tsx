import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PlasmaSnapshot } from "../services/api";

interface PlasmaWindChartProps {
  points: PlasmaSnapshot[];
  dangerSpeedKms?: number;
}

export function PlasmaWindChart({ points, dangerSpeedKms = 600 }: PlasmaWindChartProps) {
  if (points.length === 0) {
    return <p className="empty-state">Plasma stream waiting for first sample.</p>;
  }

  const data = points.map((point) => ({
    time: new Date(point.observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    speed: Number(point.speed_kms.toFixed(1)),
    density: Number(point.density_pcm3.toFixed(2)),
  }));

  return (
    <div className="chart-wrap reveal-rise">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="4 4" stroke="#255070" />
          <XAxis dataKey="time" stroke="#9ac1d9" minTickGap={18} />
          <YAxis yAxisId="left" stroke="#9ac1d9" />
          <YAxis yAxisId="right" orientation="right" stroke="#f5b172" />
          <ReferenceLine yAxisId="left" y={dangerSpeedKms} stroke="#f25f5c" strokeDasharray="5 5" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f2d44",
              border: "1px solid #2f6388",
              borderRadius: "12px",
            }}
          />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="speed" stroke="#72cbf8" strokeWidth={2.2} dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="density" stroke="#f4a259" strokeWidth={2.2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="chart-note">Dashed line marks plasma speed danger threshold ({dangerSpeedKms} km/s).</p>
    </div>
  );
}
