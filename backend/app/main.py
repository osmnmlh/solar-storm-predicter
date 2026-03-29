from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.alerts import router as alerts_router
from app.api.routes.status import router as status_router
from app.clients.donki_client import DonkiClient
from app.clients.swpc_client import SWPCClient
from app.config import get_settings
from app.services.alert_service import AlertService
from app.services.alert_intel_service import AlertIntelService
from app.services.email_notifier import EmailNotifier
from app.services.risk_engine import build_risk_snapshot, estimate_roti_proxy
from app.services.storage_service import StorageService
from app.services.state import RuntimeState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def collector_loop(app: FastAPI) -> None:
    settings = app.state.settings
    runtime = app.state.runtime
    swpc_client = app.state.swpc_client
    donki_client = app.state.donki_client
    alert_intel_service = app.state.alert_intel_service
    storage_service = app.state.storage_service
    alert_service = app.state.alert_service
    notifier = app.state.email_notifier

    while not app.state.stop_event.is_set():
        cycle_started_at = perf_counter()
        try:
            outcome, plasma_outcome, magnetic_outcome, alerts_outcome, donki_summary = await asyncio.gather(
                swpc_client.get_latest_observation(),
                swpc_client.get_latest_plasma(),
                swpc_client.get_latest_bz(),
                swpc_client.get_alert_bulletins(),
                donki_client.get_recent_summary(),
            )

            alert_intel_summary = await alert_intel_service.analyze_alerts(
                alerts_outcome.alerts,
                details=alerts_outcome.details,
            )

            details_parts: list[str] = []
            if outcome.details:
                details_parts.append(f"SWPC: {outcome.details}")
            if plasma_outcome.details:
                details_parts.append(f"Plasma: {plasma_outcome.details}")
            if magnetic_outcome.details:
                details_parts.append(f"Magnetic: {magnetic_outcome.details}")
            if alerts_outcome.details:
                details_parts.append(f"Alerts: {alerts_outcome.details}")
            if donki_summary.source_status == "error" and donki_summary.details:
                details_parts.append(f"DONKI: {donki_summary.details}")
            if alert_intel_summary.source_status == "error" and alert_intel_summary.details:
                details_parts.append(f"AlertIntel: {alert_intel_summary.details}")

            bz_value = magnetic_outcome.bz_nt
            plasma_speed = plasma_outcome.plasma.speed_kms if plasma_outcome.plasma is not None else None
            roti_value = outcome.observation.roti_tecu_min
            if roti_value is None and settings.roti_fallback_enabled:
                roti_value = estimate_roti_proxy(
                    kp=outcome.observation.kp,
                    bz_nt=bz_value if bz_value is not None else -3.0,
                    speed_kms=plasma_speed if plasma_speed is not None else 420.0,
                    xray_flux=outcome.observation.xray_flux,
                )

            enriched_observation = outcome.observation.model_copy(
                update={
                    "bz_nt": bz_value,
                    "roti_tecu_min": roti_value,
                }
            )

            async with runtime.lock:
                runtime.latest_observation = enriched_observation
                runtime.recent_observations.append(enriched_observation)
                if plasma_outcome.plasma is not None:
                    runtime.latest_plasma = plasma_outcome.plasma
                    runtime.recent_plasma.append(plasma_outcome.plasma)
                runtime.donki_summary = donki_summary
                runtime.noaa_alert_intel = alert_intel_summary
                runtime.risk_snapshot = build_risk_snapshot(
                    enriched_observation,
                    runtime.recent_observations,
                    donki_summary=donki_summary,
                    plasma_speed_kms=plasma_speed,
                    bz_nt=bz_value,
                    roti_tecu_min=roti_value,
                )
                runtime.source_health.mode = "mock" if outcome.used_mock else "live"
                runtime.source_health.details = " | ".join(details_parts) if details_parts else None
                runtime.source_health.last_successful_fetch = datetime.now(timezone.utc)
                if outcome.used_mock:
                    runtime.source_health.consecutive_failures += 1
                else:
                    runtime.source_health.consecutive_failures = 0
                runtime.pipeline_stats.collector_cycles += 1
                runtime.pipeline_stats.last_cycle_ms = round((perf_counter() - cycle_started_at) * 1000, 2)

                risk_snapshot = runtime.risk_snapshot
                source_mode = runtime.source_health.mode

            if risk_snapshot is not None:
                new_alerts = alert_service.evaluate_snapshot(risk_snapshot)
                for alert in new_alerts:
                    await notifier.send_alert(alert)

            storage_service.save_snapshot(
                captured_at=datetime.now(timezone.utc),
                source_mode=source_mode,
                observation=enriched_observation,
                plasma=plasma_outcome.plasma,
                risk=risk_snapshot,
                donki_summary=donki_summary,
                noaa_alert_intel=alert_intel_summary,
                active_alerts=alert_service.active_count(),
            )

        except Exception as exc:
            logger.exception("Collector iteration failed")
            async with runtime.lock:
                runtime.source_health.mode = "error"
                runtime.source_health.details = str(exc)
                runtime.source_health.consecutive_failures += 1
                runtime.pipeline_stats.collector_cycles += 1
                runtime.pipeline_stats.last_cycle_ms = round((perf_counter() - cycle_started_at) * 1000, 2)

        try:
            await asyncio.wait_for(app.state.stop_event.wait(), timeout=settings.poll_interval_seconds)
        except TimeoutError:
            continue


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.stop_event.clear()
        app.state.collector_task = asyncio.create_task(collector_loop(app))
        logger.info("Collector started")
        try:
            yield
        finally:
            app.state.stop_event.set()
            task = app.state.collector_task
            if task:
                await task
            logger.info("Collector stopped")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.runtime = RuntimeState()
    app.state.swpc_client = SWPCClient(settings)
    app.state.donki_client = DonkiClient(settings)
    app.state.alert_intel_service = AlertIntelService(settings)
    app.state.storage_service = StorageService(
        sqlite_file=settings.storage_sqlite_file,
        enabled=settings.storage_enabled,
    )
    app.state.alert_service = AlertService(
        cooldown_minutes=settings.alert_cooldown_minutes,
        max_history=settings.max_alert_history,
    )
    app.state.email_notifier = EmailNotifier(settings)
    app.state.stop_event = asyncio.Event()
    app.state.collector_task = None

    app.include_router(status_router, prefix="/api")
    app.include_router(alerts_router, prefix="/api")

    return app


app = create_app()
