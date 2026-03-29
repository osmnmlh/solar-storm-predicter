import { NoaaAlertIntelSummary } from "../services/api";

interface NoaaAlertIntelFeedProps {
  summary: NoaaAlertIntelSummary | null;
}

export function NoaaAlertIntelFeed({ summary }: NoaaAlertIntelFeedProps) {
  if (!summary) {
    return <p className="empty-state">NOAA alert intelligence waiting for collector sync.</p>;
  }

  if (summary.source_status !== "live") {
    return <p className="empty-state">NOAA alert intelligence is {summary.source_status}. {summary.details ?? "No details"}</p>;
  }

  if (summary.records.length === 0) {
    return (
      <div className="intel-meta">
        <p>
          No new important bulletin yet. New scanned: {summary.new_alerts_seen}, important detected: {summary.important_alerts}.
        </p>
      </div>
    );
  }

  return (
    <div className="intel-wrap reveal-rise">
      <p className="intel-meta">
        Last check: {new Date(summary.checked_at).toLocaleString()} | New scanned: {summary.new_alerts_seen} | Important: {summary.important_alerts}
      </p>
      <div className="intel-list">
        {summary.records.slice(0, 12).map((record) => (
          <article key={`${record.issue_datetime}-${record.message.slice(0, 20)}`} className="intel-item">
            <header>
              <strong>{new Date(record.issue_datetime).toLocaleString()}</strong>
              <span className={record.ai_analysis.suitable ? "chip chip-danger" : "chip chip-muted"}>
                AI suitable: {String(record.ai_analysis.suitable)}
              </span>
            </header>
            <p>{record.message}</p>
            <footer>
              <span className="chip">Kp: {record.kp_value ?? "-"}</span>
              <span className="chip">G: {record.g_scale ?? "-"}</span>
              <span className="chip">X-Ray: {record.xray_class ?? "-"}</span>
              <span className="chip">Radio: {record.radio_emission ?? "-"}</span>
            </footer>
            <p className="intel-risk">Local risk: {record.local_risk}</p>
            <p className="intel-ai-impact">AI impact: {record.ai_analysis.technical_impact}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
