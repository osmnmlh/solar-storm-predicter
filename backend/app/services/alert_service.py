from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas import AlertRecord, RiskSnapshot


class AlertService:
    def __init__(self, cooldown_minutes: int = 30, max_history: int = 200) -> None:
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._history: deque[AlertRecord] = deque(maxlen=max_history)
        self._active: dict[str, AlertRecord] = {}
        self._last_triggered_by_key: dict[str, datetime] = {}

    def evaluate_snapshot(self, risk: RiskSnapshot, now: datetime | None = None) -> list[AlertRecord]:
        current_time = now or datetime.now(timezone.utc)
        created_alerts: list[AlertRecord] = []

        if risk.overall_severity >= 3:
            dedupe_key = (
                f"sev:{risk.overall_severity}|"
                f"g:{risk.geomagnetic.code}|s:{risk.solar_radiation.code}|r:{risk.radio_blackout.code}"
            )
            last_triggered = self._last_triggered_by_key.get(dedupe_key)
            if last_triggered is None or (current_time - last_triggered) >= self.cooldown:
                alert = AlertRecord(
                    id=str(uuid4()),
                    created_at=current_time,
                    updated_at=current_time,
                    level=risk.overall_level,
                    title="Space weather risk escalation",
                    message=(
                        "Composite risk reached "
                        f"{risk.overall_level.upper()} with NOAA components "
                        f"G={risk.geomagnetic.code}, S={risk.solar_radiation.code}, R={risk.radio_blackout.code}."
                    ),
                    status="open",
                    source="system",
                    dedupe_key=dedupe_key,
                )
                self._active[alert.id] = alert
                self._history.appendleft(alert)
                self._last_triggered_by_key[dedupe_key] = current_time
                created_alerts.append(alert)
        elif risk.overall_severity <= 1 and self._active:
            closed_items = []
            for active in list(self._active.values()):
                closed = active.model_copy(
                    update={
                        "status": "closed",
                        "updated_at": current_time,
                        "closed_at": current_time,
                        "note": "Auto-closed due to calm conditions",
                    }
                )
                self._history.appendleft(closed)
                closed_items.append(active.id)
            for alert_id in closed_items:
                self._active.pop(alert_id, None)

        return created_alerts

    def create_manual_alert(
        self,
        *,
        level: str,
        title: str,
        message: str,
        now: datetime | None = None,
    ) -> AlertRecord:
        current_time = now or datetime.now(timezone.utc)
        alert = AlertRecord(
            id=str(uuid4()),
            created_at=current_time,
            updated_at=current_time,
            level=level,
            title=title,
            message=message,
            status="open",
            source="manual",
            dedupe_key=f"manual:{level}:{title}",
        )
        self._active[alert.id] = alert
        self._history.appendleft(alert)
        return alert

    def acknowledge_alert(self, alert_id: str, note: str | None = None) -> AlertRecord:
        current_time = datetime.now(timezone.utc)
        active = self._active.get(alert_id)
        if active is None:
            raise KeyError(alert_id)

        updated = active.model_copy(
            update={
                "status": "acknowledged",
                "updated_at": current_time,
                "acknowledged_at": current_time,
                "note": note,
            }
        )
        self._active[alert_id] = updated
        self._history.appendleft(updated)
        return updated

    def close_alert(self, alert_id: str, note: str | None = None) -> AlertRecord:
        current_time = datetime.now(timezone.utc)
        active = self._active.get(alert_id)
        if active is None:
            raise KeyError(alert_id)

        updated = active.model_copy(
            update={
                "status": "closed",
                "updated_at": current_time,
                "closed_at": current_time,
                "note": note,
            }
        )
        self._active.pop(alert_id, None)
        self._history.appendleft(updated)
        return updated

    def list_active(self) -> list[AlertRecord]:
        return list(self._active.values())

    def list_alerts(self, limit: int = 50) -> list[AlertRecord]:
        return list(self._history)[: max(1, limit)]

    def active_count(self) -> int:
        return len(self._active)
