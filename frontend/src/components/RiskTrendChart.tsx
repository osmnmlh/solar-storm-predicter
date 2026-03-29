import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RiskSnapshot } from "../services/api";

interface RiskTrendChartProps {
  risk: RiskSnapshot | null;
}

export function RiskTrendChart({ risk }: RiskTrendChartProps) {
  if (!risk) {
    return <p className="empty-state">Waiting for first risk snapshot...</p>;
  }

  const drivers = risk.driver_scores ?? {};
  const data = [
    {
      name: "Geomagnetic",
      severity: risk.geomagnetic.severity,
      code: risk.geomagnetic.code,
      driver: drivers.geomagnetic ?? 0,
    },
    {
      name: "Radiation",
      severity: risk.solar_radiation.severity,
      code: risk.solar_radiation.code,
      driver: drivers.solar_radiation ?? 0,
    },
    {
      name: "Blackout",
      severity: risk.radio_blackout.severity,
      code: risk.radio_blackout.code,
      driver: drivers.radio_blackout ?? 0,
    },
  ];

  return (
    <div className="chart-wrap reveal-rise">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} barGap={16}>
          <CartesianGrid strokeDasharray="4 4" stroke="#255070" />
          <ReferenceLine y={1} stroke="#5eb9ea" strokeDasharray="5 5" />
          <ReferenceLine y={3} stroke="#f25f5c" strokeDasharray="5 5" />
          <XAxis dataKey="name" stroke="#9ac1d9" />
          <YAxis domain={[0, 5]} stroke="#9ac1d9" />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === "severity") {
                return [`${value}/5`, "NOAA Component"];
              }
              return [value.toFixed(2), "Weighted Driver"];
            }}
            contentStyle={{
              backgroundColor: "#0f2d44",
              border: "1px solid #2f6388",
              borderRadius: "12px",
            }}
          />
          <Bar dataKey="severity" fill="#f4a259" radius={[8, 8, 2, 2]} minPointSize={8}>
            <LabelList dataKey="code" position="top" fill="#ffd3a0" />
          </Bar>
          <Line type="monotone" dataKey="driver" stroke="#72cbf8" strokeWidth={2.2} dot={{ r: 4 }} />
        </BarChart>
      </ResponsiveContainer>
      <p className="chart-note">Blue line shows weighted contribution of each component to the composite model.</p>
    </div>
  );
}
