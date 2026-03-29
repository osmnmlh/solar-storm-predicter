import { ForecastPoint } from "../services/api";
import { SeverityBadge } from "./SeverityBadge";

interface ForecastTimelineProps {
  points: ForecastPoint[];
}

export function ForecastTimeline({ points }: ForecastTimelineProps) {
  if (points.length === 0) {
    return <p className="empty-state">Forecast timeline will appear after first collector cycle.</p>;
  }

  return (
    <div className="forecast-grid reveal-rise">
      {points.map((point) => (
        <article key={point.horizon_hours} className="forecast-card">
          <header>
            <h4>+{point.horizon_hours}h</h4>
            <SeverityBadge level={point.predicted_level} />
          </header>
          <strong>Severity {point.predicted_severity}/5</strong>
          <p>Confidence {Math.round(point.confidence * 100)}%</p>
        </article>
      ))}
    </div>
  );
}
