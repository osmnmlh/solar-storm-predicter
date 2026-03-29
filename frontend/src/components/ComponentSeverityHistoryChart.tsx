import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Observation } from "../services/api";

interface ComponentSeverityHistoryChartProps {
  points: Observation[];
}

function geomagneticSeverity(kp: number): number {
  if (kp >= 9) return 5;
  if (kp >= 8) return 4;
  if (kp >= 7) return 3;
  if (kp >= 6) return 2;
  if (kp >= 5) return 1;
  return 0;
}

function radiationSeverity(proton: number): number {
  if (proton >= 1e5) return 5;
  if (proton >= 1e4) return 4;
  if (proton >= 1e3) return 3;
  if (proton >= 1e2) return 2;
  if (proton >= 10) return 1;
  return 0;
}

function blackoutSeverity(xray: number): number {
  if (xray >= 2e-3) return 5;
  if (xray >= 1e-3) return 4;
  if (xray >= 1e-4) return 3;
  if (xray >= 5e-5) return 2;
  if (xray >= 1e-5) return 1;
  return 0;
}

export function ComponentSeverityHistoryChart({ points }: ComponentSeverityHistoryChartProps) {
  if (points.length === 0) {
    return <p className="empty-state">Severity history will appear after first collector samples.</p>;
  }

  const data = points.map((point) => {
    const g = geomagneticSeverity(point.kp);
    const s = radiationSeverity(point.proton_flux_10mev);
    const r = blackoutSeverity(point.xray_flux);
    return {
      time: new Date(point.observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      geomagnetic: g,
      radiation: s,
      blackout: r,
      overall: Math.max(g, s, r),
    };
  });

  return (
    <div className="chart-wrap reveal-rise">
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="4 4" stroke="#255070" />
          <ReferenceLine y={1} stroke="#5eb9ea" strokeDasharray="4 4" />
          <ReferenceLine y={3} stroke="#f25f5c" strokeDasharray="4 4" />
          <XAxis dataKey="time" stroke="#9ac1d9" minTickGap={18} />
          <YAxis domain={[0, 5]} stroke="#9ac1d9" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f2d44",
              border: "1px solid #2f6388",
              borderRadius: "12px",
            }}
          />
          <Legend />
          <Area type="monotone" dataKey="geomagnetic" stroke="#72cbf8" fill="#72cbf833" strokeWidth={2} />
          <Area type="monotone" dataKey="radiation" stroke="#f4a259" fill="#f4a25933" strokeWidth={2} />
          <Area type="monotone" dataKey="blackout" stroke="#ff6f6f" fill="#ff6f6f33" strokeWidth={2} />
          <Area type="monotone" dataKey="overall" stroke="#f9d76d" fill="#f9d76d30" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
      <p className="chart-note">Severity traces are derived from NOAA G/S/R thresholds over the observation buffer.</p>
    </div>
  );
}
