from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import (
    DonkiSummary,
    NoaaAlertIntelSummary,
    PersistedSnapshotRecord,
    PlasmaSnapshot,
    RiskSnapshot,
    SpaceWeatherObservation,
    StorageStatsResponse,
)


class StorageService:
    def __init__(self, sqlite_file: str, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()
        self._db_path = self._resolve_path(sqlite_file)
        if self.enabled:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()

    def save_snapshot(
        self,
        *,
        captured_at: datetime,
        source_mode: str,
        observation: SpaceWeatherObservation | None,
        plasma: PlasmaSnapshot | None,
        risk: RiskSnapshot | None,
        donki_summary: DonkiSummary | None,
        noaa_alert_intel: NoaaAlertIntelSummary | None,
        active_alerts: int,
    ) -> None:
        if not self.enabled:
            return

        payload = {
            "captured_at": captured_at.isoformat(),
            "source_mode": source_mode,
            "active_alerts": active_alerts,
            "observation": observation.model_dump(mode="json") if observation is not None else None,
            "plasma": plasma.model_dump(mode="json") if plasma is not None else None,
            "risk": risk.model_dump(mode="json") if risk is not None else None,
            "donki_summary": donki_summary.model_dump(mode="json") if donki_summary is not None else None,
            "noaa_alert_intel": noaa_alert_intel.model_dump(mode="json") if noaa_alert_intel is not None else None,
        }

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO telemetry_snapshots (
                        captured_at,
                        source_mode,
                        kp,
                        speed_kms,
                        bz_nt,
                        roti_tecu_min,
                        proton_flux_10mev,
                        xray_flux,
                        overall_level,
                        overall_severity,
                        scenario_code,
                        scenario_color,
                        combination_signature,
                        event_pressure,
                        composite_score,
                        donki_event_count,
                        important_alerts,
                        active_alerts,
                        raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        captured_at.isoformat(),
                        source_mode,
                        observation.kp if observation is not None else None,
                        plasma.speed_kms if plasma is not None else None,
                        observation.bz_nt if observation is not None else None,
                        observation.roti_tecu_min if observation is not None else None,
                        observation.proton_flux_10mev if observation is not None else None,
                        observation.xray_flux if observation is not None else None,
                        risk.overall_level if risk is not None else None,
                        risk.overall_severity if risk is not None else None,
                        risk.combined_scenario.code if risk is not None and risk.combined_scenario is not None else None,
                        risk.combined_scenario.color if risk is not None and risk.combined_scenario is not None else None,
                        risk.combination_signature if risk is not None else None,
                        risk.event_pressure if risk is not None else None,
                        risk.composite_score if risk is not None else None,
                        donki_summary.event_count if donki_summary is not None else None,
                        noaa_alert_intel.important_alerts if noaa_alert_intel is not None else None,
                        active_alerts,
                        json.dumps(payload, ensure_ascii=True),
                    ),
                )
                conn.commit()

    def get_recent(self, limit: int = 200) -> list[PersistedSnapshotRecord]:
        if not self.enabled:
            return []

        safe_limit = max(1, min(limit, 2000))
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT captured_at, source_mode, kp, speed_kms, bz_nt, roti_tecu_min, proton_flux_10mev,
                           xray_flux, overall_level, overall_severity, scenario_code, scenario_color, combination_signature
                    FROM telemetry_snapshots
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()

        records: list[PersistedSnapshotRecord] = []
        for row in rows:
            records.append(
                PersistedSnapshotRecord(
                    captured_at=self._parse_time(row[0]),
                    source_mode=str(row[1]),
                    kp=float(row[2]) if row[2] is not None else None,
                    speed_kms=float(row[3]) if row[3] is not None else None,
                    bz_nt=float(row[4]) if row[4] is not None else None,
                    roti_tecu_min=float(row[5]) if row[5] is not None else None,
                    proton_flux_10mev=float(row[6]) if row[6] is not None else None,
                    xray_flux=float(row[7]) if row[7] is not None else None,
                    overall_level=str(row[8]) if row[8] is not None else None,
                    overall_severity=int(row[9]) if row[9] is not None else None,
                    scenario_code=str(row[10]) if row[10] is not None else None,
                    scenario_color=str(row[11]) if row[11] is not None else None,
                    combination_signature=str(row[12]) if row[12] is not None else None,
                )
            )
        return records

    def get_stats(self) -> StorageStatsResponse:
        if not self.enabled:
            return StorageStatsResponse(total_snapshots=0, first_snapshot_at=None, last_snapshot_at=None)

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*), MIN(captured_at), MAX(captured_at)
                    FROM telemetry_snapshots
                    """
                ).fetchone()

        total = int(row[0]) if row and row[0] is not None else 0
        first = self._parse_time(row[1]) if row and row[1] else None
        last = self._parse_time(row[2]) if row and row[2] else None
        return StorageStatsResponse(total_snapshots=total, first_snapshot_at=first, last_snapshot_at=last)

    def _init_schema(self) -> None:
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        captured_at TEXT NOT NULL,
                        source_mode TEXT NOT NULL,
                        kp REAL,
                        speed_kms REAL,
                        bz_nt REAL,
                        roti_tecu_min REAL,
                        proton_flux_10mev REAL,
                        xray_flux REAL,
                        overall_level TEXT,
                        overall_severity INTEGER,
                        scenario_code TEXT,
                        scenario_color TEXT,
                        combination_signature TEXT,
                        event_pressure REAL,
                        composite_score REAL,
                        donki_event_count INTEGER,
                        important_alerts INTEGER,
                        active_alerts INTEGER,
                        raw_json TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_telemetry_captured_at ON telemetry_snapshots (captured_at DESC)"
                )
                conn.commit()

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        backend_root = Path(__file__).resolve().parents[2]
        return backend_root / path

    def _parse_time(self, value: str) -> datetime:
        text = value.strip()
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
