import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTimeline } from "../components/AlertTimeline";
import { CombinedScenarioPanel } from "../components/CombinedScenarioPanel";
import { ComponentSeverityHistoryChart } from "../components/ComponentSeverityHistoryChart";
import { DonkiEventPulseChart } from "../components/DonkiEventPulseChart";
import { ForecastTimeline } from "../components/ForecastTimeline";
import { IngestionPlanPanel } from "../components/IngestionPlanPanel";
import { MetricCard } from "../components/MetricCard";
import { NoaaAlertIntelFeed } from "../components/NoaaAlertIntelFeed";
import { ObservationHistoryChart } from "../components/ObservationHistoryChart";
import { PlasmaWindChart } from "../components/PlasmaWindChart";
import { RiskTrendChart } from "../components/RiskTrendChart";
import { SeverityBadge } from "../components/SeverityBadge";
import {
  ForecastPoint,
  HistoryResponse,
  AlertRecord,
  ApiIngestionPlanResponse,
  PlasmaHistoryResponse,
  StorageStatsResponse,
  StatusResponse,
  acknowledgeAlert,
  closeAlert,
  fetchAlerts,
  fetchForecast,
  fetchHistory,
  fetchIngestionPlan,
  fetchPlasmaHistory,
  fetchStorageStats,
  fetchStatus,
  triggerTestAlert,
} from "../services/api";

const REFRESH_INTERVAL_MS = 60_000;
const QUICK_RETRY_INTERVAL_MS = 8_000;

export function DashboardPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [plasmaHistory, setPlasmaHistory] = useState<PlasmaHistoryResponse | null>(null);
  const [ingestionPlan, setIngestionPlan] = useState<ApiIngestionPlanResponse | null>(null);
  const [storageStats, setStorageStats] = useState<StorageStatsResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [sendingTest, setSendingTest] = useState(false);
  const [busyAlertId, setBusyAlertId] = useState<string | null>(null);
  const [testLevel, setTestLevel] = useState<"minor" | "moderate" | "strong" | "severe" | "critical">(
    "strong",
  );

  const loadData = useCallback(async () => {
    try {
      const [statusData, alertData, historyData, plasmaHistoryData, forecastData, planData, storageStatsData] =
        await Promise.all([
        fetchStatus(),
        fetchAlerts(40),
        fetchHistory(120),
        fetchPlasmaHistory(120),
        fetchForecast(),
        fetchIngestionPlan(),
        fetchStorageStats(),
      ]);
      setStatus(statusData);
      setAlerts(alertData);
      setHistory(historyData);
      setPlasmaHistory(plasmaHistoryData);
      setForecast(forecastData);
      setIngestionPlan(planData);
      setStorageStats(storageStatsData);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = window.setInterval(loadData, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    if (!loading && !status?.risk) {
      const retryTimer = window.setTimeout(() => {
        void loadData();
      }, QUICK_RETRY_INTERVAL_MS);
      return () => window.clearTimeout(retryTimer);
    }
    return undefined;
  }, [loadData, loading, status?.risk]);

  const observation = status?.latest_observation;
  const plasma = status?.latest_plasma;
  const risk = status?.risk;
  const donki = status?.donki_summary ?? null;
  const noaaIntel = status?.noaa_alert_intel ?? null;
  const historyPoints = history?.points ?? [];
  const plasmaPoints = plasmaHistory?.points ?? [];

  const sourceLabel = useMemo(() => {
    if (!status) return "Unknown";
    if (status.source_health.mode === "live") return "Live NOAA feed";
    if (status.source_health.mode === "mock") return "Fallback mock feed";
    return "Source error";
  }, [status]);

  async function handleTestAlert() {
    try {
      setSendingTest(true);
      await triggerTestAlert({
        level: testLevel,
        title: `Manual ${testLevel} panel test`,
        message: "Operator initiated stress-test alert from dashboard",
      });
      await loadData();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSendingTest(false);
    }
  }

  async function handleRefreshNow() {
    setLoading(true);
    await loadData();
  }

  async function handleAcknowledge(alertId: string) {
    try {
      setBusyAlertId(alertId);
      await acknowledgeAlert(alertId, "Acknowledged from panel");
      await loadData();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyAlertId(null);
    }
  }

  async function handleClose(alertId: string) {
    try {
      setBusyAlertId(alertId);
      await closeAlert(alertId, "Closed by operator");
      await loadData();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyAlertId(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="aurora-layer" />
      <section className="dashboard">
        <header className="hero reveal-fade">
          <div>
            <p className="kicker">Space Weather Early Warning</p>
            <h1>Gunes Firtinalari Erken Uyari Paneli</h1>
            <p className="subtitle">
              6-24 saatlik elektromanyetik firtina riski, canli NOAA akisi, trend analizi ve
              operasyonel alarm yasam dongusu.
            </p>
          </div>
          <div className="hero-actions">
            <label className="inline-select">
              Test Level
              <select
                value={testLevel}
                onChange={(event) =>
                  setTestLevel(event.target.value as "minor" | "moderate" | "strong" | "severe" | "critical")
                }
              >
                <option value="minor">minor</option>
                <option value="moderate">moderate</option>
                <option value="strong">strong</option>
                <option value="severe">severe</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <button onClick={handleTestAlert} disabled={sendingTest || loading}>
              {sendingTest ? "Sending..." : "Trigger Test Alert"}
            </button>
            <button className="ghost-button" onClick={handleRefreshNow} disabled={loading}>
              {loading ? "Refreshing..." : "Refresh Now"}
            </button>
            {risk ? <SeverityBadge level={risk.overall_level} /> : null}
          </div>
        </header>

        {error ? <p className="error-banner">{error}</p> : null}

        <section className="metrics-grid">
          <MetricCard title="Feed Mode" value={sourceLabel} subValue={status?.source_health.details ?? "Operational"} />
          <MetricCard
            title="Kp Index"
            value={observation ? observation.kp.toFixed(2) : "-"}
            subValue={observation ? new Date(observation.observed_at).toLocaleString() : "Awaiting data"}
          />
          <MetricCard
            title="IMF Bz"
            value={observation?.bz_nt != null ? `${observation.bz_nt.toFixed(2)} nT` : "-"}
            subValue={risk?.bz_band ? risk.bz_band.label : "Awaiting magnetic feed"}
          />
          <MetricCard
            title="ROTI"
            value={observation?.roti_tecu_min != null ? `${observation.roti_tecu_min.toFixed(2)} TECU/min` : "-"}
            subValue={risk?.roti_band ? risk.roti_band.label : "Awaiting ROTI estimate"}
          />
          <MetricCard
            title="X-ray Flux"
            value={observation ? observation.xray_flux.toExponential(2) : "-"}
            subValue={risk ? `R-level: ${risk.radio_blackout.code}` : "No R-level yet"}
          />
          <MetricCard
            title=">=10 MeV Proton"
            value={observation ? observation.proton_flux_10mev.toFixed(2) : "-"}
            subValue={risk ? `S-level: ${risk.solar_radiation.code}` : "No S-level yet"}
          />
          <MetricCard
            title="Solar Wind Speed"
            value={plasma ? `${plasma.speed_kms.toFixed(1)} km/s` : "-"}
            subValue={plasma ? `Status: ${plasma.speed_status}` : "Awaiting plasma feed"}
          />
          <MetricCard
            title="Solar Wind Density"
            value={plasma ? `${plasma.density_pcm3.toFixed(2)} p/cm3` : "-"}
            subValue={plasma ? new Date(plasma.observed_at).toLocaleString() : "Awaiting plasma feed"}
          />
          <MetricCard
            title="Active Alerts"
            value={String(status?.active_alerts ?? 0)}
            subValue={status ? `Failures: ${status.source_health.consecutive_failures}` : "-"}
          />
          <MetricCard
            title="Collector Health"
            value={status ? `${status.pipeline_stats.collector_cycles} cycles` : "-"}
            subValue={status ? `Last cycle ${status.pipeline_stats.last_cycle_ms} ms` : "-"}
          />
          <MetricCard
            title="Forecast Confidence"
            value={risk ? `${Math.round(risk.confidence * 100)}%` : "-"}
            subValue={risk ? `${risk.horizon_start_hours}-${risk.horizon_end_hours}h horizon` : "-"}
          />
          <MetricCard
            title="Composite Score"
            value={risk ? risk.composite_score.toFixed(2) : "-"}
            subValue={risk ? `Overall ${risk.overall_severity}/5` : "-"}
          />
          <MetricCard
            title="DONKI Event Pulse"
            value={donki ? `${donki.event_count}` : "-"}
            subValue={donki ? `${donki.source_status} / weighted ${donki.weighted_score.toFixed(2)}` : "Awaiting event feed"}
          />
          <MetricCard
            title="External Event Pressure"
            value={risk ? risk.event_pressure.toFixed(1) : "-"}
            subValue={donki?.top_event ?? "No dominant DONKI event"}
          />
          <MetricCard
            title="NOAA Important Alerts"
            value={noaaIntel ? `${noaaIntel.important_alerts}` : "-"}
            subValue={noaaIntel ? `New scanned: ${noaaIntel.new_alerts_seen}` : "Alert intel initializing"}
          />
          <MetricCard
            title="DB Snapshots"
            value={storageStats ? String(storageStats.total_snapshots) : "-"}
            subValue={storageStats?.last_snapshot_at ? `Last: ${new Date(storageStats.last_snapshot_at).toLocaleString()}` : "No snapshot yet"}
          />
        </section>

        <section className="content-grid">
          <article className="panel-card">
            <header>
              <h2>Combined Risk Mapping</h2>
              <p>Speed + Bz + Kp + Proton + X-ray + ROTI kombinasyonunun sektorel etkileri.</p>
            </header>
            <CombinedScenarioPanel risk={risk ?? null} />
          </article>

          <article className="panel-card">
            <header>
              <h2>Component Severity</h2>
              <p>NOAA G / S / R scales with model driver weighting and severity evolution.</p>
            </header>
            <RiskTrendChart risk={risk ?? null} />
            <ComponentSeverityHistoryChart points={historyPoints} />
            {risk ? <p className="explanation">{risk.explanation}</p> : null}
            {risk ? (
              <ul className="impact-list">
                {risk.impact_summary.map((impact) => (
                  <li key={impact}>{impact}</li>
                ))}
              </ul>
            ) : null}
          </article>

          <article className="panel-card">
            <header>
              <h2>Alert Timeline</h2>
              <p>Latest generated and manual alerts.</p>
            </header>
            {loading ? (
              <p className="empty-state">Loading dashboard...</p>
            ) : (
              <AlertTimeline
                alerts={alerts}
                busyAlertId={busyAlertId}
                onAcknowledge={handleAcknowledge}
                onClose={handleClose}
              />
            )}
          </article>
        </section>

        <section className="content-grid content-grid-alt">
          <article className="panel-card">
            <header>
              <h2>Observation History</h2>
              <p>
                Last {history?.window_hours ?? "-"}h trend window from in-memory collector buffer.
              </p>
            </header>
            <ObservationHistoryChart points={historyPoints} />
          </article>

          <article className="panel-card">
            <header>
              <h2>Forecast Timeline</h2>
              <p>Projected severity points over 6, 12 and 24 hours.</p>
            </header>
            <ForecastTimeline points={forecast.length > 0 ? forecast : risk?.forecast_timeline ?? []} />
            {risk?.trends.length ? (
              <div className="trend-strip">
                {risk.trends.map((item) => (
                  <span key={item.metric} className={`trend-chip trend-${item.trend}`}>
                    {item.metric}: {item.trend} ({item.slope})
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        </section>

        <section className="content-grid content-grid-alt">
          <article className="panel-card">
            <header>
              <h2>L1 Plasma Telemetry</h2>
              <p>Real-time solar wind speed and density from NOAA plasma stream.</p>
            </header>
            <PlasmaWindChart points={plasmaPoints} />
          </article>

          <article className="panel-card">
            <header>
              <h2>NOAA Bulletin Intelligence</h2>
              <p>Regex-filtered critical bulletins with Gemini-assisted technical impact summary.</p>
            </header>
            <NoaaAlertIntelFeed summary={noaaIntel} />
          </article>
        </section>

        <section className="content-grid-single">
          <article className="panel-card">
            <header>
              <h2>API Polling ve Database Plani</h2>
              <p>Hangi metrik hangi API'den, kac dakikada bir cekiliyor ve DB'ye nasil yaziliyor.</p>
            </header>
            <IngestionPlanPanel plan={ingestionPlan} storageStats={storageStats} />
          </article>

          <article className="panel-card">
            <header>
              <h2>Solar Event Pulse (NASA DONKI)</h2>
              <p>External event intelligence layer for CME/FLR/SEP/GST pressure on the 6-24h forecast.</p>
            </header>
            <DonkiEventPulseChart summary={donki} />
          </article>
        </section>
      </section>
    </main>
  );
}
