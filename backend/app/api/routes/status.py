from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from app.schemas import (
    ApiIngestionPlanResponse,
    DonkiSummary,
    ForecastPoint,
    HistoryResponse,
    NoaaAlertIntelSummary,
    PersistedSnapshotRecord,
    PlasmaHistoryResponse,
    StorageStatsResponse,
    StatusResponse,
)
from app.services.ingestion_plan_service import build_ingestion_plan

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    runtime = request.app.state.runtime
    alert_service = request.app.state.alert_service

    async with runtime.lock:
        latest_observation = runtime.latest_observation
        latest_plasma = runtime.latest_plasma
        risk = runtime.risk_snapshot
        donki_summary = runtime.donki_summary
        noaa_alert_intel = runtime.noaa_alert_intel
        source_health = runtime.source_health
        pipeline_stats = runtime.pipeline_stats

    return StatusResponse(
        source_health=source_health,
        pipeline_stats=pipeline_stats,
        latest_observation=latest_observation,
        latest_plasma=latest_plasma,
        risk=risk,
        donki_summary=donki_summary,
        noaa_alert_intel=noaa_alert_intel,
        active_alerts=alert_service.active_count(),
        used_mock_data=source_health.mode == "mock",
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(request: Request, limit: int = Query(default=72, ge=6, le=288)) -> HistoryResponse:
    runtime = request.app.state.runtime

    async with runtime.lock:
        points = list(runtime.recent_observations)[-limit:]

    window_hours = max(1, round(limit / 12))
    return HistoryResponse(points=points, window_hours=window_hours)


@router.get("/plasma/history", response_model=PlasmaHistoryResponse)
async def get_plasma_history(request: Request, limit: int = Query(default=72, ge=6, le=288)) -> PlasmaHistoryResponse:
    runtime = request.app.state.runtime

    async with runtime.lock:
        points = list(runtime.recent_plasma)[-limit:]

    window_hours = max(1, round(limit / 12))
    return PlasmaHistoryResponse(points=points, window_hours=window_hours)


@router.get("/forecast", response_model=list[ForecastPoint])
async def get_forecast(request: Request) -> list[ForecastPoint]:
    runtime = request.app.state.runtime
    async with runtime.lock:
        risk = runtime.risk_snapshot
    if risk is None:
        return []
    return risk.forecast_timeline


@router.get("/events/donki", response_model=DonkiSummary)
async def get_donki_events(request: Request) -> DonkiSummary:
    runtime = request.app.state.runtime
    settings = request.app.state.settings

    async with runtime.lock:
        summary = runtime.donki_summary

    if summary is not None:
        return summary

    return DonkiSummary(
        retrieved_at=datetime.now(timezone.utc),
        source_status="disabled" if not settings.donki_enabled else "error",
        lookback_days=settings.donki_lookback_days,
        details="DONKI snapshot not available yet",
    )


@router.get("/alerts/intel", response_model=NoaaAlertIntelSummary)
async def get_noaa_alert_intelligence(request: Request) -> NoaaAlertIntelSummary:
    runtime = request.app.state.runtime
    settings = request.app.state.settings

    async with runtime.lock:
        summary = runtime.noaa_alert_intel

    if summary is not None:
        return summary

    return NoaaAlertIntelSummary(
        checked_at=datetime.now(timezone.utc),
        source_status="disabled" if not settings.noaa_alert_intel_enabled else "error",
        details="NOAA alert intelligence snapshot not available yet",
    )


@router.get("/ingestion/plan", response_model=ApiIngestionPlanResponse)
async def get_ingestion_plan(request: Request) -> ApiIngestionPlanResponse:
    settings = request.app.state.settings
    return build_ingestion_plan(settings)


@router.get("/storage/stats", response_model=StorageStatsResponse)
async def get_storage_stats(request: Request) -> StorageStatsResponse:
    storage_service = request.app.state.storage_service
    return storage_service.get_stats()


@router.get("/storage/recent", response_model=list[PersistedSnapshotRecord])
async def get_storage_recent(request: Request, limit: int = Query(default=120, ge=1, le=2000)) -> list[PersistedSnapshotRecord]:
    storage_service = request.app.state.storage_service
    return storage_service.get_recent(limit)


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
