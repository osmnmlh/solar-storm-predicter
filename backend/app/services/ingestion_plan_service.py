from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.schemas import ApiIngestionPlanItem, ApiIngestionPlanResponse


def build_ingestion_plan(settings: Settings) -> ApiIngestionPlanResponse:
    base_items = [
        ApiIngestionPlanItem(
            source="NOAA SWPC",
            metric="Solar wind speed + density",
            endpoint=settings.swpc_plasma_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="Speed seviyeleri (Yesil/Sari/Turuncu/Kirmizi) ve drag riski icin",
        ),
        ApiIngestionPlanItem(
            source="NOAA SWPC",
            metric="Interplanetary magnetic field Bz",
            endpoint=settings.swpc_mag_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="Bz manyetik kapi durumunu belirlemek icin",
        ),
        ApiIngestionPlanItem(
            source="NOAA SWPC",
            metric="Planetary Kp index",
            endpoint=settings.swpc_kp_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="G1-G5 firtina siddeti ve sektor etkileri icin",
        ),
        ApiIngestionPlanItem(
            source="NOAA SWPC / GOES",
            metric="X-ray flux (0.1-0.8nm)",
            endpoint=settings.swpc_xray_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="R1-R5 radio blackout riskini hesaplamak icin",
        ),
        ApiIngestionPlanItem(
            source="NOAA SWPC / GOES",
            metric=">=10 MeV proton flux",
            endpoint=settings.swpc_proton_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="S1-S5 radyasyon ve SEU risklerini belirlemek icin",
        ),
        ApiIngestionPlanItem(
            source="NOAA SWPC",
            metric="Operational alerts bulletin",
            endpoint=settings.swpc_alerts_url,
            poll_interval_minutes=5,
            save_table="telemetry_snapshots",
            reason="Regex + Gemini ile kritik bulletin analizi icin",
        ),
        ApiIngestionPlanItem(
            source="NASA DONKI",
            metric="CME/FLR/SEP/GST external event pressure",
            endpoint=f"{settings.donki_base_url}/<EVENT_TYPE>",
            poll_interval_minutes=settings.donki_refresh_minutes,
            save_table="telemetry_snapshots",
            reason="Dis olay baskisi ile risk ivmelenmesini yakalamak icin",
        ),
    ]

    if settings.roti_enabled and settings.roti_api_url:
        base_items.append(
            ApiIngestionPlanItem(
                source="Configured ROTI Provider",
                metric="ROTI (TECU/min)",
                endpoint=settings.roti_api_url,
                poll_interval_minutes=5,
                save_table="telemetry_snapshots",
                reason="GNSS scintillation ve anti-spoofing dayanimi icin",
            )
        )
    else:
        base_items.append(
            ApiIngestionPlanItem(
                source="Internal Zenith Model",
                metric="ROTI proxy",
                endpoint="derived://kp-bz-speed-xray",
                poll_interval_minutes=5,
                save_table="telemetry_snapshots",
                reason="Harici ROTI akisi yoksa Kp/Bz/Speed/X-ray kombinasyonundan tahmin",
            )
        )

    return ApiIngestionPlanResponse(generated_at=datetime.now(timezone.utc), items=base_items)
