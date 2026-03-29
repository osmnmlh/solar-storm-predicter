from __future__ import annotations

import asyncio
import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas import AlertAiAnalysis, NoaaAlertIntelRecord, NoaaAlertIntelSummary

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - optional dependency path
    genai = None
    types = None


class AlertIntelService:
    REGEX_KP = re.compile(r"Kp\s*(?:-index of\s*)?=?\s*([0-9])", re.IGNORECASE)
    REGEX_G_SCALE = re.compile(r"G([1-5])", re.IGNORECASE)
    REGEX_XRAY = re.compile(r"([MX]\d+(?:\.\d+)?)", re.IGNORECASE)
    REGEX_RADIO = re.compile(r"Type\s*(II|IV)\s*Radio\s*Emission", re.IGNORECASE)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._records: deque[NoaaAlertIntelRecord] = deque(maxlen=settings.noaa_alert_intel_max_records)
        self._memory_file = self._resolve_path(settings.noaa_alert_memory_file)
        self._report_file = self._resolve_path(settings.noaa_alert_report_file)
        self._last_processed_issue_datetime = self._read_memory()

        self._gemini_client = None
        if (
            settings.gemini_enabled
            and settings.gemini_api_key
            and settings.gemini_api_key.strip()
            and genai is not None
        ):
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key.strip())

    async def analyze_alerts(self, alerts_payload: list[dict], details: str | None = None) -> NoaaAlertIntelSummary:
        checked_at = datetime.now(timezone.utc)

        if not self.settings.noaa_alert_intel_enabled:
            return self._summary(
                checked_at=checked_at,
                source_status="disabled",
                details="NOAA alert intelligence is disabled",
            )

        alerts = self._sort_alerts_by_issue_datetime(alerts_payload)
        if not alerts:
            return self._summary(
                checked_at=checked_at,
                source_status="error" if details else "live",
                details=details or "No alert payload received",
            )

        if self._last_processed_issue_datetime is None:
            latest_issue_datetime = self._parse_issue_datetime(alerts[-1].get("issue_datetime", ""))
            if latest_issue_datetime is not None:
                self._last_processed_issue_datetime = latest_issue_datetime
                self._write_memory(latest_issue_datetime)
            return self._summary(
                checked_at=checked_at,
                source_status="live",
                details=(
                    "NOAA alert memory initialized with latest issue timestamp"
                    if latest_issue_datetime is not None
                    else "NOAA alert memory initialization skipped due to invalid timestamp"
                ),
            )

        new_alerts = [
            item
            for item in alerts
            if (parsed := self._parse_issue_datetime(item.get("issue_datetime", ""))) is not None
            and parsed > self._last_processed_issue_datetime
        ]

        important_count = 0
        for index, item in enumerate(new_alerts):
            issue_datetime = self._parse_issue_datetime(item.get("issue_datetime", ""))
            if issue_datetime is None:
                continue

            message = str(item.get("message", "")).strip()
            if self._is_important_alert(message):
                important_count += 1
                record = await self._build_record(issue_datetime, message)
                self._records.appendleft(record)
                self._append_report(record)

                if self.settings.ai_cooldown_seconds > 0 and index < len(new_alerts) - 1:
                    await asyncio.sleep(self.settings.ai_cooldown_seconds)

            self._last_processed_issue_datetime = issue_datetime

        if self._last_processed_issue_datetime is not None:
            self._write_memory(self._last_processed_issue_datetime)

        return self._summary(
            checked_at=checked_at,
            source_status="live",
            new_alerts_seen=len(new_alerts),
            important_alerts=important_count,
            details=details,
        )

    async def _build_record(self, issue_datetime: datetime, message: str) -> NoaaAlertIntelRecord:
        kp_match = self.REGEX_KP.search(message)
        g_match = self.REGEX_G_SCALE.search(message)
        xray_match = self.REGEX_XRAY.search(message)
        radio_match = self.REGEX_RADIO.search(message)

        g_value = int(g_match.group(1)) if g_match else None
        local_risk = self._regional_risk(g_value)
        ai_analysis = await self._analyze_with_gemini(message)

        return NoaaAlertIntelRecord(
            issue_datetime=issue_datetime,
            kp_value=int(kp_match.group(1)) if kp_match else None,
            g_scale=g_value,
            xray_class=xray_match.group(1).upper() if xray_match else None,
            radio_emission=radio_match.group(1).upper() if radio_match else None,
            local_risk=local_risk,
            ai_analysis=ai_analysis,
            message=message,
        )

    async def _analyze_with_gemini(self, message: str) -> AlertAiAnalysis:
        if self._gemini_client is None or types is None:
            return AlertAiAnalysis(
                suitable=False,
                technical_impact="Gemini disabled or API key not configured",
                model=None,
            )

        prompt = (
            "Asagidaki NOAA uzay hava durumu bultenini analiz et. "
            "Sadece JSON don: {\"uygun_mu\": true/false, \"teknik_etki\": \"maksimum 15 kelime\"}.\n"
            f"Mesaj: {message}"
        )

        def run_sync() -> AlertAiAnalysis:
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                text = (response.text or "").strip()
                payload: dict[str, Any] = json.loads(text) if text else {}

                suitable = bool(payload.get("uygun_mu", False))
                technical_impact = str(payload.get("teknik_etki", "No AI impact text"))[:220]

                return AlertAiAnalysis(
                    suitable=suitable,
                    technical_impact=technical_impact,
                    model=self.settings.gemini_model,
                )
            except Exception as exc:
                return AlertAiAnalysis(
                    suitable=False,
                    technical_impact=f"Gemini API error: {exc}",
                    model=self.settings.gemini_model,
                )

        return await asyncio.to_thread(run_sync)

    def _summary(
        self,
        *,
        checked_at: datetime,
        source_status: str,
        new_alerts_seen: int = 0,
        important_alerts: int = 0,
        details: str | None = None,
    ) -> NoaaAlertIntelSummary:
        return NoaaAlertIntelSummary(
            checked_at=checked_at,
            source_status=source_status,
            last_processed_issue_datetime=self._last_processed_issue_datetime,
            new_alerts_seen=new_alerts_seen,
            important_alerts=important_alerts,
            records=list(self._records),
            memory_file=str(self._memory_file),
            report_file=str(self._report_file),
            details=details,
        )

    def _is_important_alert(self, message: str) -> bool:
        return bool(
            self.REGEX_KP.search(message)
            or self.REGEX_G_SCALE.search(message)
            or self.REGEX_XRAY.search(message)
            or self.REGEX_RADIO.search(message)
        )

    def _regional_risk(self, g_scale: int | None) -> str:
        if g_scale is None:
            return "Risk degerlendirilemedi"
        if g_scale <= 2:
            return "Dusuk (Turkiye icin belirgin etki beklenmiyor)"
        if g_scale == 3:
            return "Orta (HF radyo iletisiminde kisa sureli parazit riski)"
        if g_scale == 4:
            return "Yuksek (GPS sapmalari ve uydu sarjlanmasi riski)"
        if g_scale >= 5:
            return "Kritik (sebeke dalgalanmasi ve iletisim kesintisi riski)"
        return "Bilinmiyor"

    def _sort_alerts_by_issue_datetime(self, alerts_payload: list[dict]) -> list[dict]:
        parsed: list[tuple[datetime, dict]] = []
        for item in alerts_payload:
            issue_datetime = self._parse_issue_datetime(item.get("issue_datetime", ""))
            if issue_datetime is not None:
                parsed.append((issue_datetime, item))
        parsed.sort(key=lambda entry: entry[0])
        return [item for _, item in parsed]

    def _append_report(self, record: NoaaAlertIntelRecord) -> None:
        self._report_file.parent.mkdir(parents=True, exist_ok=True)
        report_line = (
            f"[{record.issue_datetime.isoformat()}] "
            f"Kp={record.kp_value if record.kp_value is not None else '-'} "
            f"G={record.g_scale if record.g_scale is not None else '-'} "
            f"XRay={record.xray_class or '-'} Radio={record.radio_emission or '-'} | "
            f"LocalRisk={record.local_risk} | "
            f"AI(suitable={record.ai_analysis.suitable}, impact={record.ai_analysis.technical_impact})"
        )
        with self._report_file.open("a", encoding="utf-8") as file:
            file.write(report_line + "\n")

    def _read_memory(self) -> datetime | None:
        if not self._memory_file.exists():
            return None
        try:
            raw = self._memory_file.read_text(encoding="utf-8").strip()
            return self._parse_issue_datetime(raw)
        except Exception:
            return None

    def _write_memory(self, value: datetime) -> None:
        self._memory_file.parent.mkdir(parents=True, exist_ok=True)
        self._memory_file.write_text(value.isoformat(), encoding="utf-8")

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        backend_root = Path(__file__).resolve().parents[2]
        return backend_root / path

    def _parse_issue_datetime(self, value: str) -> datetime | None:
        text = str(value).strip()
        if not text:
            return None

        try:
            if text.endswith("Z"):
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
