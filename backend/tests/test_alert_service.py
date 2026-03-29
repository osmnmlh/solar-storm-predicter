from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas import RiskSnapshot, ScaleLevel
from app.services.alert_service import AlertService


def _risk(*, severity: int, level: str = "strong") -> RiskSnapshot:
    return RiskSnapshot(
        generated_at=datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc),
        overall_level=level,
        overall_severity=severity,
        composite_score=float(severity),
        confidence=0.8,
        geomagnetic=ScaleLevel(code="G3" if severity >= 3 else "G1", severity=min(severity, 5)),
        solar_radiation=ScaleLevel(code="S1", severity=1),
        radio_blackout=ScaleLevel(code="R1", severity=1),
        trends=[],
        forecast_timeline=[],
        impact_summary=[],
        explanation="test",
    )


def test_dedupe_and_cooldown() -> None:
    service = AlertService(cooldown_minutes=30, max_history=50)
    now = datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc)

    first = service.evaluate_snapshot(_risk(severity=3), now=now)
    second = service.evaluate_snapshot(_risk(severity=3), now=now + timedelta(minutes=10))
    third = service.evaluate_snapshot(_risk(severity=3), now=now + timedelta(minutes=31))

    assert len(first) == 1
    assert len(second) == 0
    assert len(third) == 1


def test_closes_active_alerts_when_calm() -> None:
    service = AlertService(cooldown_minutes=30, max_history=50)
    now = datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc)

    service.evaluate_snapshot(_risk(severity=4, level="severe"), now=now)
    assert service.active_count() == 1

    service.evaluate_snapshot(_risk(severity=1, level="minor"), now=now + timedelta(minutes=5))
    assert service.active_count() == 0


def test_acknowledge_and_close_alert() -> None:
    service = AlertService(cooldown_minutes=30, max_history=50)
    now = datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc)

    created = service.evaluate_snapshot(_risk(severity=4, level="severe"), now=now)[0]
    acked = service.acknowledge_alert(created.id, note="Operator acknowledged")
    assert acked.status == "acknowledged"
    assert acked.acknowledged_at is not None

    closed = service.close_alert(created.id, note="Resolved")
    assert closed.status == "closed"
    assert closed.closed_at is not None
    assert service.active_count() == 0
