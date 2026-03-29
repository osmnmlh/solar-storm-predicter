export interface ScaleLevel {
  code: string;
  severity: number;
}

export interface PipelineStats {
  collector_cycles: number;
  last_cycle_ms: number;
}

export interface TrendSignal {
  metric: "kp" | "xray_flux" | "proton_flux_10mev";
  trend: "rising" | "falling" | "stable";
  slope: number;
}

export interface MetricBand {
  metric: string;
  code: string;
  label: string;
  color: "green" | "yellow" | "orange" | "red";
  severity: number;
  description: string;
}

export interface CombinedRiskScenario {
  code: string;
  name: string;
  color: "green" | "yellow" | "orange" | "red";
  severity: number;
  analysis: string;
}

export interface ForecastPoint {
  horizon_hours: number;
  predicted_severity: number;
  predicted_level: "calm" | "minor" | "moderate" | "strong" | "severe" | "extreme";
  confidence: number;
}

export interface DonkiEvent {
  event_id: string;
  event_type: string;
  started_at: string;
  score: number;
  summary: string;
  source_url: string | null;
}

export interface DonkiSummary {
  retrieved_at: string;
  source_status: "live" | "disabled" | "error";
  lookback_days: number;
  event_count: number;
  weighted_score: number;
  max_event_score: number;
  top_event: string | null;
  events: DonkiEvent[];
  details: string | null;
}

export interface SourceHealth {
  mode: "live" | "mock" | "error";
  last_successful_fetch: string | null;
  consecutive_failures: number;
  details: string | null;
}

export interface Observation {
  observed_at: string;
  kp: number;
  bz_nt: number | null;
  roti_tecu_min: number | null;
  xray_flux: number;
  proton_flux_10mev: number;
  source: "live" | "mock";
}

export interface PlasmaSnapshot {
  observed_at: string;
  density_pcm3: number;
  speed_kms: number;
  speed_status: "normal" | "danger";
  source: "live" | "mock";
}

export interface AlertAiAnalysis {
  suitable: boolean;
  technical_impact: string;
  model: string | null;
}

export interface NoaaAlertIntelRecord {
  issue_datetime: string;
  kp_value: number | null;
  g_scale: number | null;
  xray_class: string | null;
  radio_emission: string | null;
  local_risk: string;
  ai_analysis: AlertAiAnalysis;
  message: string;
}

export interface NoaaAlertIntelSummary {
  checked_at: string;
  source_status: "live" | "disabled" | "error";
  last_processed_issue_datetime: string | null;
  new_alerts_seen: number;
  important_alerts: number;
  records: NoaaAlertIntelRecord[];
  memory_file: string | null;
  report_file: string | null;
  details: string | null;
}

export interface RiskSnapshot {
  generated_at: string;
  horizon_start_hours: number;
  horizon_end_hours: number;
  overall_level: "calm" | "minor" | "moderate" | "strong" | "severe" | "extreme";
  overall_severity: number;
  composite_score: number;
  event_pressure: number;
  confidence: number;
  geomagnetic: ScaleLevel;
  solar_radiation: ScaleLevel;
  radio_blackout: ScaleLevel;
  driver_scores: Record<string, number>;
  speed_band: MetricBand | null;
  bz_band: MetricBand | null;
  kp_band: MetricBand | null;
  proton_band: MetricBand | null;
  xray_band: MetricBand | null;
  roti_band: MetricBand | null;
  combined_scenario: CombinedRiskScenario | null;
  combination_signature: string | null;
  likely_issues: string[];
  recommended_actions: string[];
  trends: TrendSignal[];
  forecast_timeline: ForecastPoint[];
  impact_summary: string[];
  explanation: string;
}

export interface AlertRecord {
  id: string;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  closed_at: string | null;
  level: string;
  title: string;
  message: string;
  status: "open" | "closed" | "acknowledged";
  source: "system" | "manual";
  dedupe_key: string;
  note: string | null;
}

export interface StatusResponse {
  source_health: SourceHealth;
  pipeline_stats: PipelineStats;
  latest_observation: Observation | null;
  latest_plasma: PlasmaSnapshot | null;
  risk: RiskSnapshot | null;
  donki_summary: DonkiSummary | null;
  noaa_alert_intel: NoaaAlertIntelSummary | null;
  active_alerts: number;
  used_mock_data: boolean;
}

export interface HistoryResponse {
  points: Observation[];
  window_hours: number;
}

export interface PlasmaHistoryResponse {
  points: PlasmaSnapshot[];
  window_hours: number;
}

export interface ApiIngestionPlanItem {
  source: string;
  metric: string;
  endpoint: string;
  poll_interval_minutes: number;
  save_table: string;
  reason: string;
}

export interface ApiIngestionPlanResponse {
  generated_at: string;
  items: ApiIngestionPlanItem[];
}

export interface PersistedSnapshotRecord {
  captured_at: string;
  source_mode: string;
  kp: number | null;
  speed_kms: number | null;
  bz_nt: number | null;
  roti_tecu_min: number | null;
  proton_flux_10mev: number | null;
  xray_flux: number | null;
  overall_level: string | null;
  overall_severity: number | null;
  scenario_code: string | null;
  scenario_color: string | null;
  combination_signature: string | null;
}

export interface StorageStatsResponse {
  total_snapshots: number;
  first_snapshot_at: string | null;
  last_snapshot_at: string | null;
}

const defaultApiBase =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000/api`
    : "http://localhost:8000/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? defaultApiBase;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`API ${response.status}: ${message}`);
  }

  return response.json() as Promise<T>;
}

export function fetchStatus(): Promise<StatusResponse> {
  return requestJson<StatusResponse>("/status");
}

export function fetchAlerts(limit = 50): Promise<AlertRecord[]> {
  return requestJson<AlertRecord[]>(`/alerts?limit=${limit}`);
}

export function fetchHistory(limit = 96): Promise<HistoryResponse> {
  return requestJson<HistoryResponse>(`/history?limit=${limit}`);
}

export function fetchForecast(): Promise<ForecastPoint[]> {
  return requestJson<ForecastPoint[]>("/forecast");
}

export function fetchPlasmaHistory(limit = 96): Promise<PlasmaHistoryResponse> {
  return requestJson<PlasmaHistoryResponse>(`/plasma/history?limit=${limit}`);
}

export function fetchDonkiEvents(): Promise<DonkiSummary> {
  return requestJson<DonkiSummary>("/events/donki");
}

export function fetchIngestionPlan(): Promise<ApiIngestionPlanResponse> {
  return requestJson<ApiIngestionPlanResponse>("/ingestion/plan");
}

export function fetchStorageStats(): Promise<StorageStatsResponse> {
  return requestJson<StorageStatsResponse>("/storage/stats");
}

export function fetchStorageRecent(limit = 120): Promise<PersistedSnapshotRecord[]> {
  return requestJson<PersistedSnapshotRecord[]>(`/storage/recent?limit=${limit}`);
}

export function triggerTestAlert(payload?: {
  level?: "minor" | "moderate" | "strong" | "severe" | "critical";
  title?: string;
  message?: string;
}): Promise<AlertRecord> {
  return requestJson<AlertRecord>("/alerts/test", {
    method: "POST",
    body: JSON.stringify({
      level: payload?.level ?? "strong",
      title: payload?.title ?? "Manual panel test",
      message: payload?.message ?? "Operator triggered test alert from dashboard",
    }),
  });
}

export function acknowledgeAlert(alertId: string, note?: string): Promise<AlertRecord> {
  return requestJson<AlertRecord>(`/alerts/${alertId}/ack`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export function closeAlert(alertId: string, note?: string): Promise<AlertRecord> {
  return requestJson<AlertRecord>(`/alerts/${alertId}/close`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}
