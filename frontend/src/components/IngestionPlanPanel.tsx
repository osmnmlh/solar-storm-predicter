import { ApiIngestionPlanResponse, StorageStatsResponse } from "../services/api";

interface IngestionPlanPanelProps {
  plan: ApiIngestionPlanResponse | null;
  storageStats: StorageStatsResponse | null;
}

export function IngestionPlanPanel({ plan, storageStats }: IngestionPlanPanelProps) {
  if (!plan) {
    return <p className="empty-state">Ingestion plan is loading...</p>;
  }

  return (
    <div className="ingestion-wrap reveal-rise">
      <p className="ingestion-meta">
        Generated: {new Date(plan.generated_at).toLocaleString()} | Stored snapshots: {storageStats?.total_snapshots ?? "-"}
      </p>
      <div className="ingestion-table-wrap">
        <table className="ingestion-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Metric</th>
              <th>Interval (min)</th>
              <th>Endpoint</th>
              <th>DB Table</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((item) => (
              <tr key={`${item.source}-${item.metric}`}>
                <td>{item.source}</td>
                <td>{item.metric}</td>
                <td>{item.poll_interval_minutes}</td>
                <td>{item.endpoint}</td>
                <td>{item.save_table}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="ingestion-reason-list">
        {plan.items.map((item) => (
          <li key={`${item.metric}-reason`}>
            <strong>{item.metric}:</strong> {item.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
