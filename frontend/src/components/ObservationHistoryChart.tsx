import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { Observation } from "../services/api";

interface ObservationHistoryChartProps {
  points: Observation[];
}

export function ObservationHistoryChart({ points }: ObservationHistoryChartProps) {
  if (points.length === 0) {
    return <p className="empty-state">No observation history yet.</p>;
  }

  const data = points.map((point) => ({
    time: new Date(point.observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    kp: Number(point.kp.toFixed(2)),
    proton: Number(point.proton_flux_10mev.toFixed(2)),
    xray: Number((point.xray_flux * 100000).toFixed(3)),
  }));

  return (
    <div className="chart-wrap reveal-rise">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="4 4" stroke="#255070" />
          <XAxis dataKey="time" stroke="#9ac1d9" minTickGap={20} />
          <YAxis yAxisId="left" stroke="#9ac1d9" />
          <YAxis yAxisId="right" orientation="right" stroke="#f5b172" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f2d44",
              border: "1px solid #2f6388",
              borderRadius: "12px",
            }}
          />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="kp" stroke="#72cbf8" strokeWidth={2} dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="proton" stroke="#f4a259" strokeWidth={2} dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="xray" stroke="#ff6f6f" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="chart-note">X-ray values are scaled by 100000 for readability.</p>
    </div>
  );
}
