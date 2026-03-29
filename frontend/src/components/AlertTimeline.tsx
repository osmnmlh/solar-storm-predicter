import { AlertRecord } from "../services/api";

interface AlertTimelineProps {
  alerts: AlertRecord[];
  onAcknowledge?: (alertId: string) => Promise<void>;
  onClose?: (alertId: string) => Promise<void>;
  busyAlertId?: string | null;
}

export function AlertTimeline({ alerts, onAcknowledge, onClose, busyAlertId }: AlertTimelineProps) {
  if (alerts.length === 0) {
    return <p className="empty-state">No alerts yet. Monitoring is active.</p>;
  }

  return (
    <div className="timeline reveal-rise">
      {alerts.map((alert) => (
        <article key={alert.id} className={`timeline-item status-${alert.status}`}>
          <div className="timeline-marker" />
          <div className="timeline-content">
            <header>
              <h4>{alert.title}</h4>
              <span>{new Date(alert.created_at).toLocaleString()}</span>
            </header>
            <p>{alert.message}</p>
            <footer>
              <span className="chip">{alert.level.toUpperCase()}</span>
              <span className="chip chip-muted">{alert.source}</span>
              <span className="chip chip-muted">{alert.status}</span>
              {alert.note ? <span className="chip chip-muted">note: {alert.note}</span> : null}
            </footer>
            {alert.status !== "closed" ? (
              <div className="timeline-actions">
                {alert.status === "open" ? (
                  <button
                    className="ghost-button"
                    disabled={busyAlertId === alert.id}
                    onClick={() => {
                      if (onAcknowledge) {
                        void onAcknowledge(alert.id);
                      }
                    }}
                  >
                    Acknowledge
                  </button>
                ) : null}
                <button
                  className="ghost-button"
                  disabled={busyAlertId === alert.id}
                  onClick={() => {
                    if (onClose) {
                      void onClose(alert.id);
                    }
                  }}
                >
                  Close
                </button>
              </div>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
