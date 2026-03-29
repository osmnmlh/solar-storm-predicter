from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScaleLevel(BaseModel):
    code: str
    severity: int = Field(ge=0, le=5)


class SpaceWeatherObservation(BaseModel):
    observed_at: datetime
    kp: float = Field(ge=0)
    bz_nt: float | None = None
    roti_tecu_min: float | None = Field(default=None, ge=0)
    xray_flux: float = Field(ge=0)
    proton_flux_10mev: float = Field(ge=0)
    source: Literal["live", "mock"] = "live"


class PlasmaSnapshot(BaseModel):
    observed_at: datetime
    density_pcm3: float = Field(ge=0)
    speed_kms: float = Field(ge=0)
    speed_status: Literal["normal", "danger"] = "normal"
    source: Literal["live", "mock"] = "live"


class SourceHealth(BaseModel):
    mode: Literal["live", "mock", "error"] = "live"
    last_successful_fetch: datetime | None = None
    consecutive_failures: int = 0
    details: str | None = None


class PipelineStats(BaseModel):
    collector_cycles: int = 0
    last_cycle_ms: float = Field(default=0, ge=0)


class TrendSignal(BaseModel):
    metric: Literal["kp", "xray_flux", "proton_flux_10mev"]
    trend: Literal["rising", "falling", "stable"]
    slope: float


class ForecastPoint(BaseModel):
    horizon_hours: int = Field(ge=1, le=72)
    predicted_severity: int = Field(ge=0, le=5)
    predicted_level: str
    confidence: float = Field(ge=0, le=1)


class DonkiEvent(BaseModel):
    event_id: str
    event_type: str
    started_at: datetime
    score: float = Field(ge=0)
    summary: str
    source_url: str | None = None


class DonkiSummary(BaseModel):
    retrieved_at: datetime
    source_status: Literal["live", "disabled", "error"] = "disabled"
    lookback_days: int = Field(default=3, ge=1, le=30)
    event_count: int = Field(default=0, ge=0)
    weighted_score: float = Field(default=0, ge=0)
    max_event_score: float = Field(default=0, ge=0)
    top_event: str | None = None
    events: list[DonkiEvent] = Field(default_factory=list)
    details: str | None = None


class AlertAiAnalysis(BaseModel):
    suitable: bool = False
    technical_impact: str
    model: str | None = None


class NoaaAlertIntelRecord(BaseModel):
    issue_datetime: datetime
    kp_value: int | None = None
    g_scale: int | None = None
    xray_class: str | None = None
    radio_emission: str | None = None
    local_risk: str
    ai_analysis: AlertAiAnalysis
    message: str


class NoaaAlertIntelSummary(BaseModel):
    checked_at: datetime
    source_status: Literal["live", "disabled", "error"] = "disabled"
    last_processed_issue_datetime: datetime | None = None
    new_alerts_seen: int = Field(default=0, ge=0)
    important_alerts: int = Field(default=0, ge=0)
    records: list[NoaaAlertIntelRecord] = Field(default_factory=list)
    memory_file: str | None = None
    report_file: str | None = None
    details: str | None = None


class MetricBand(BaseModel):
    metric: str
    code: str
    label: str
    color: Literal["green", "yellow", "orange", "red"]
    severity: int = Field(ge=0, le=3)
    description: str


class CombinedRiskScenario(BaseModel):
    code: str
    name: str
    color: Literal["green", "yellow", "orange", "red"]
    severity: int = Field(ge=0, le=5)
    analysis: str


class RiskSnapshot(BaseModel):
    generated_at: datetime
    horizon_start_hours: int = 6
    horizon_end_hours: int = 24
    overall_level: str
    overall_severity: int = Field(ge=0, le=5)
    composite_score: float = Field(ge=0)
    event_pressure: float = Field(default=0, ge=0)
    confidence: float = Field(ge=0, le=1)
    geomagnetic: ScaleLevel
    solar_radiation: ScaleLevel
    radio_blackout: ScaleLevel
    driver_scores: dict[str, float] = Field(default_factory=dict)
    speed_band: MetricBand | None = None
    bz_band: MetricBand | None = None
    kp_band: MetricBand | None = None
    proton_band: MetricBand | None = None
    xray_band: MetricBand | None = None
    roti_band: MetricBand | None = None
    combined_scenario: CombinedRiskScenario | None = None
    combination_signature: str | None = None
    likely_issues: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    trends: list[TrendSignal] = Field(default_factory=list)
    forecast_timeline: list[ForecastPoint] = Field(default_factory=list)
    impact_summary: list[str] = Field(default_factory=list)
    explanation: str


class AlertRecord(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    closed_at: datetime | None = None
    level: str
    title: str
    message: str
    status: Literal["open", "closed", "acknowledged"]
    source: Literal["system", "manual"]
    dedupe_key: str
    note: str | None = None


class StatusResponse(BaseModel):
    source_health: SourceHealth
    pipeline_stats: PipelineStats
    latest_observation: SpaceWeatherObservation | None
    latest_plasma: PlasmaSnapshot | None = None
    risk: RiskSnapshot | None
    donki_summary: DonkiSummary | None = None
    noaa_alert_intel: NoaaAlertIntelSummary | None = None
    active_alerts: int
    used_mock_data: bool


class HistoryResponse(BaseModel):
    points: list[SpaceWeatherObservation]
    window_hours: int


class PlasmaHistoryResponse(BaseModel):
    points: list[PlasmaSnapshot]
    window_hours: int


class ApiIngestionPlanItem(BaseModel):
    source: str
    metric: str
    endpoint: str
    poll_interval_minutes: int = Field(ge=1)
    save_table: str
    reason: str


class ApiIngestionPlanResponse(BaseModel):
    generated_at: datetime
    items: list[ApiIngestionPlanItem]


class PersistedSnapshotRecord(BaseModel):
    captured_at: datetime
    source_mode: str
    kp: float | None = None
    speed_kms: float | None = None
    bz_nt: float | None = None
    roti_tecu_min: float | None = None
    proton_flux_10mev: float | None = None
    xray_flux: float | None = None
    overall_level: str | None = None
    overall_severity: int | None = None
    scenario_code: str | None = None
    scenario_color: str | None = None
    combination_signature: str | None = None


class StorageStatsResponse(BaseModel):
    total_snapshots: int = 0
    first_snapshot_at: datetime | None = None
    last_snapshot_at: datetime | None = None


class TestAlertRequest(BaseModel):
    level: Literal["minor", "moderate", "strong", "severe", "critical"] = "strong"
    title: str = "Manual test alert"
    message: str = "Manual trigger from operator panel"


class AlertActionRequest(BaseModel):
    note: str | None = None
