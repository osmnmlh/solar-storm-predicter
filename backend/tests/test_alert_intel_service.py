from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.services.alert_intel_service import AlertIntelService


def _alerts(*timestamps: str) -> list[dict]:
    payload: list[dict] = []
    for idx, issue_datetime in enumerate(timestamps):
        payload.append(
            {
                "issue_datetime": issue_datetime,
                "message": f"ALERT idx={idx} Kp=6 G3 Type II Radio Emission and X1.2 flare",
            }
        )
    return payload


def test_bootstrap_skips_historical_alerts() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        settings = Settings(
            gemini_enabled=False,
            noaa_alert_memory_file=str(temp_path / "memory.txt"),
            noaa_alert_report_file=str(temp_path / "report.txt"),
            ai_cooldown_seconds=0,
        )

        service = AlertIntelService(settings)
        summary = asyncio.run(
            service.analyze_alerts(
                _alerts("2026-03-29T10:00:00Z", "2026-03-29T10:30:00Z"),
            )
        )

        assert summary.new_alerts_seen == 0
        assert summary.important_alerts == 0
        assert summary.last_processed_issue_datetime is not None
        assert (temp_path / "memory.txt").exists()


def test_processes_new_important_alert_with_ai_fallback() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        settings = Settings(
            gemini_enabled=False,
            noaa_alert_memory_file=str(temp_path / "memory.txt"),
            noaa_alert_report_file=str(temp_path / "report.txt"),
            ai_cooldown_seconds=0,
        )

        service = AlertIntelService(settings)
        asyncio.run(service.analyze_alerts(_alerts("2026-03-29T10:00:00Z")))

        summary = asyncio.run(
            service.analyze_alerts(
                [
                    {
                        "issue_datetime": "2026-03-29T11:15:00Z",
                        "message": "Geomagnetic bulletin: Kp-index of 7 expected, G4 storm with Type IV Radio Emission and X2.1 flare",
                    }
                ]
            )
        )

        assert summary.new_alerts_seen == 1
        assert summary.important_alerts == 1
        assert len(summary.records) == 1

        record = summary.records[0]
        assert record.kp_value == 7
        assert record.g_scale == 4
        assert record.xray_class == "X2.1"
        assert record.radio_emission == "IV"
        assert record.ai_analysis.suitable is False
        assert "Gemini disabled" in record.ai_analysis.technical_impact

        report_text = (temp_path / "report.txt").read_text(encoding="utf-8")
        assert "LocalRisk=" in report_text
