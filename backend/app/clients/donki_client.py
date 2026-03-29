from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import Settings
from app.schemas import DonkiEvent, DonkiSummary


class DonkiClient:
    EVENT_TYPES = ("CME", "FLR", "SEP", "GST", "MPC", "RBE")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_summary: DonkiSummary | None = None
        self._cache_expires_at: datetime | None = None

    async def get_recent_summary(self) -> DonkiSummary:
        now = datetime.now(timezone.utc)

        if not self.settings.donki_enabled:
            return DonkiSummary(
                retrieved_at=now,
                source_status="disabled",
                lookback_days=self.settings.donki_lookback_days,
                details="DONKI integration is disabled",
            )

        api_key = (self.settings.donki_api_key or "").strip()
        if not api_key:
            return DonkiSummary(
                retrieved_at=now,
                source_status="disabled",
                lookback_days=self.settings.donki_lookback_days,
                details="NASA DONKI API key is not configured",
            )

        if self._cached_summary is not None and self._cache_expires_at is not None and now < self._cache_expires_at:
            return self._cached_summary

        start_date = (now - timedelta(days=self.settings.donki_lookback_days)).date().isoformat()
        end_date = now.date().isoformat()

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                payloads = await asyncio.gather(
                    *(
                        self._fetch_event_payload(
                            client=client,
                            event_type=event_type,
                            start_date=start_date,
                            end_date=end_date,
                            api_key=api_key,
                        )
                        for event_type in self.EVENT_TYPES
                    )
                )

            events: list[DonkiEvent] = []
            for event_type, payload in zip(self.EVENT_TYPES, payloads):
                events.extend(self._parse_events(event_type, payload))

            events.sort(key=lambda item: (item.score, item.started_at), reverse=True)
            trimmed_events = events[:40]

            weighted_score = round(sum(item.score for item in trimmed_events), 2)
            max_event_score = round(max((item.score for item in trimmed_events), default=0.0), 2)
            top_event = (
                f"{trimmed_events[0].event_type}: {trimmed_events[0].summary}"
                if trimmed_events
                else None
            )

            summary = DonkiSummary(
                retrieved_at=now,
                source_status="live",
                lookback_days=self.settings.donki_lookback_days,
                event_count=len(events),
                weighted_score=weighted_score,
                max_event_score=max_event_score,
                top_event=top_event,
                events=trimmed_events,
            )

            self._cached_summary = summary
            self._cache_expires_at = now + timedelta(minutes=self.settings.donki_refresh_minutes)
            return summary

        except Exception as exc:
            if self._cached_summary is not None:
                return self._cached_summary.model_copy(
                    update={
                        "details": f"Using cached DONKI data because live fetch failed: {exc}",
                    }
                )

            return DonkiSummary(
                retrieved_at=now,
                source_status="error",
                lookback_days=self.settings.donki_lookback_days,
                details=f"DONKI fetch failed: {exc}",
            )

    async def _fetch_event_payload(
        self,
        *,
        client: httpx.AsyncClient,
        event_type: str,
        start_date: str,
        end_date: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        url = f"{self.settings.donki_base_url}/{event_type}"
        retries = self.settings.request_retries
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = await client.get(
                    url,
                    params={
                        "startDate": start_date,
                        "endDate": end_date,
                        "api_key": api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    return [item for item in payload if isinstance(item, dict)]
                return []
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise RuntimeError(f"DONKI endpoint {event_type} failed: {last_error}")

    def _parse_events(self, event_type: str, payload: list[dict[str, Any]]) -> list[DonkiEvent]:
        events: list[DonkiEvent] = []

        for index, item in enumerate(payload):
            started_at = self._extract_datetime(item)
            event_id = self._extract_event_id(item, event_type, index, started_at)
            summary = self._build_summary(event_type, item)
            score = self._score_event(event_type, item)

            events.append(
                DonkiEvent(
                    event_id=event_id,
                    event_type=event_type,
                    started_at=started_at,
                    score=round(score, 2),
                    summary=summary,
                    source_url=str(item.get("link")) if item.get("link") else None,
                )
            )

        return events

    def _extract_datetime(self, item: dict[str, Any]) -> datetime:
        keys = (
            "beginTime",
            "startTime",
            "eventTime",
            "submissionTime",
            "messageIssueTime",
            "peakTime",
            "time21_5",
        )

        for key in keys:
            raw = item.get(key)
            if raw is None:
                continue
            parsed = self._parse_time(raw)
            if parsed is not None:
                return parsed

        return datetime.now(timezone.utc)

    def _extract_event_id(self, item: dict[str, Any], event_type: str, index: int, started_at: datetime) -> str:
        keys = (
            "activityID",
            "flrID",
            "gstID",
            "sepID",
            "mpcID",
            "rbeID",
            "cmeID",
        )

        for key in keys:
            value = item.get(key)
            if value:
                return str(value)

        return f"{event_type}-{started_at.strftime('%Y%m%d%H%M%S')}-{index}"

    def _build_summary(self, event_type: str, item: dict[str, Any]) -> str:
        if event_type == "FLR":
            class_type = str(item.get("classType") or "unknown")
            source_location = str(item.get("sourceLocation") or "sun region unknown")
            return f"{class_type} flare at {source_location}"

        if event_type == "GST":
            kp_values = self._gst_kp_values(item)
            if kp_values:
                return f"Geomagnetic storm with Kp up to {max(kp_values):.1f}"
            return "Geomagnetic storm event"

        if event_type == "SEP":
            instruments = item.get("instruments")
            if isinstance(instruments, list) and instruments:
                detector = instruments[0]
                if isinstance(detector, dict) and detector.get("displayName"):
                    return f"Solar energetic particle event ({detector['displayName']})"
            return "Solar energetic particle event"

        if event_type == "CME":
            analyses = item.get("cmeAnalyses")
            if isinstance(analyses, list) and analyses:
                candidate = analyses[0]
                if isinstance(candidate, dict) and candidate.get("speed") is not None:
                    return f"CME analysis with estimated speed {candidate['speed']} km/s"
            return "Coronal mass ejection detected"

        if event_type == "MPC":
            return "Magnetopause crossing event"

        if event_type == "RBE":
            return "Radiation belt enhancement"

        return "Solar event"

    def _score_event(self, event_type: str, item: dict[str, Any]) -> float:
        base_score = {
            "CME": 1.6,
            "FLR": 1.4,
            "SEP": 2.8,
            "GST": 2.2,
            "MPC": 1.2,
            "RBE": 1.0,
        }.get(event_type, 1.0)

        if event_type == "FLR":
            flare_class = str(item.get("classType") or "").upper()
            base_score = max(base_score, self._flare_score(flare_class))

        if event_type == "GST":
            kp_values = self._gst_kp_values(item)
            if kp_values:
                max_kp = max(kp_values)
                if max_kp >= 9:
                    base_score = 5.0
                elif max_kp >= 8:
                    base_score = 4.0
                elif max_kp >= 7:
                    base_score = 3.0
                elif max_kp >= 6:
                    base_score = 2.0
                elif max_kp >= 5:
                    base_score = 1.0

        return min(5.0, max(0.5, base_score))

    def _gst_kp_values(self, item: dict[str, Any]) -> list[float]:
        raw_values = item.get("allKpIndex")
        if not isinstance(raw_values, list):
            return []

        values: list[float] = []
        for entry in raw_values:
            if not isinstance(entry, dict):
                continue
            try:
                values.append(float(entry.get("kpIndex")))
            except Exception:
                continue
        return values

    def _flare_score(self, flare_class: str) -> float:
        if not flare_class:
            return 1.2

        prefix = flare_class[0]
        numeric = 1.0
        try:
            numeric = float(flare_class[1:]) if len(flare_class) > 1 else 1.0
        except ValueError:
            numeric = 1.0

        if prefix == "X":
            return min(5.0, 4.0 + numeric * 0.1)
        if prefix == "M":
            return min(4.2, 3.0 + numeric * 0.1)
        if prefix == "C":
            return min(2.0, 1.2 + numeric * 0.05)
        if prefix in {"A", "B"}:
            return 0.8
        return 1.2

    def _parse_time(self, raw_value: Any) -> datetime | None:
        text = str(raw_value).strip()
        if not text:
            return None

        try:
            if text.endswith("Z"):
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except Exception:
                continue

        return None
