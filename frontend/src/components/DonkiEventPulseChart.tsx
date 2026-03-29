import {
  Bar,
  ComposedChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DonkiSummary } from "../services/api";

interface DonkiEventPulseChartProps {
  summary: DonkiSummary | null;
}

export function DonkiEventPulseChart({ summary }: DonkiEventPulseChartProps) {
  if (!summary) {
    return <p className="empty-state">DONKI event stream is waiting for collector sync.</p>;
  }

  if (summary.source_status !== "live") {
    return <p className="empty-state">DONKI feed is {summary.source_status}. {summary.details ?? "No details"}</p>;
  }

  if (summary.events.length === 0) {
    return <p className="empty-state">No DONKI events in the selected lookback window.</p>;
  }

  const grouped = summary.events.reduce<Record<string, { count: number; score: number }>>((acc, event) => {
    const key = event.event_type;
    if (!acc[key]) {
      acc[key] = { count: 0, score: 0 };
    }
    acc[key].count += 1;
    acc[key].score += event.score;
    return acc;
  }, {});

  const chartData = Object.entries(grouped)
    .map(([eventType, value]) => ({
      eventType,
      count: value.count,
      avgScore: Number((value.score / value.count).toFixed(2)),
    }))
    .sort((a, b) => b.avgScore - a.avgScore);

  const topEvents = [...summary.events]
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  return (
    <div className="chart-wrap reveal-rise">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="4 4" stroke="#255070" />
          <XAxis dataKey="eventType" stroke="#9ac1d9" />
          <YAxis yAxisId="left" stroke="#9ac1d9" />
          <YAxis yAxisId="right" orientation="right" stroke="#f5b172" domain={[0, 5]} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f2d44",
              border: "1px solid #2f6388",
              borderRadius: "12px",
            }}
          />
          <Bar yAxisId="left" dataKey="count" fill="#72cbf8" radius={[8, 8, 2, 2]} />
          <Line yAxisId="right" dataKey="avgScore" stroke="#f4a259" strokeWidth={2.4} dot={{ r: 4 }} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="chart-note">
        DONKI lookback: {summary.lookback_days} day(s), events: {summary.event_count}, weighted score: {summary.weighted_score.toFixed(2)}.
      </p>
      <ul className="event-list">
        {topEvents.map((event) => (
          <li key={event.event_id}>
            <strong>{event.event_type}</strong> score {event.score.toFixed(2)} - {event.summary}
          </li>
        ))}
      </ul>
    </div>
  );
}
