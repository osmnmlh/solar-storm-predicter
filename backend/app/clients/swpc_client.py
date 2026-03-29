from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.schemas import PlasmaSnapshot, SpaceWeatherObservation


@dataclass
class FetchOutcome:
    observation: SpaceWeatherObservation
    used_mock: bool
    details: str | None = None


@dataclass
class PlasmaFetchOutcome:
    plasma: PlasmaSnapshot | None
    details: str | None = None


@dataclass
class AlertsFetchOutcome:
    alerts: list[dict]
    details: str | None = None


@dataclass
class MagneticFetchOutcome:
    bz_nt: float | None
    observed_at: datetime | None
    details: str | None = None


class SWPCClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mock_file = Path(__file__).resolve().parents[1] / "data" / "mock_space_weather.json"

    async def get_latest_observation(self) -> FetchOutcome:
        try:
            kp_payload = await self._fetch_json(self.settings.swpc_kp_url)
            xray_payload = await self._fetch_json(self.settings.swpc_xray_url)
            proton_payload = await self._fetch_json(self.settings.swpc_proton_url)

            kp_value, kp_time = self._extract_latest_kp(kp_payload)
            xray_value, xray_time = self._extract_latest_xray(xray_payload)
            proton_value, proton_time = self._extract_latest_proton_10mev(proton_payload)

            observed_at = max(kp_time, xray_time, proton_time)
            observation = SpaceWeatherObservation(
                observed_at=observed_at,
                kp=kp_value,
                xray_flux=xray_value,
                proton_flux_10mev=proton_value,
                source="live",
            )
            return FetchOutcome(observation=observation, used_mock=False)
        except Exception as exc:
            if not self.settings.use_mock_on_failure:
                raise
            observation = self._load_mock_observation()
            return FetchOutcome(observation=observation, used_mock=True, details=str(exc))

    async def get_latest_plasma(self) -> PlasmaFetchOutcome:
        try:
            payload = await self._fetch_json(self.settings.swpc_plasma_url)
            if not isinstance(payload, list) or len(payload) < 2:
                raise RuntimeError("Unexpected plasma payload")

            for row in reversed(payload[1:]):
                try:
                    observed_at = self._parse_time(str(row[0]))
                    density = float(row[1])
                    speed = float(row[2])
                    return PlasmaFetchOutcome(
                        plasma=PlasmaSnapshot(
                            observed_at=observed_at,
                            density_pcm3=density,
                            speed_kms=speed,
                            speed_status="danger" if speed >= self.settings.plasma_danger_speed_kms else "normal",
                            source="live",
                        )
                    )
                except Exception:
                    continue
            raise RuntimeError("No valid plasma sample found")
        except Exception as exc:
            return PlasmaFetchOutcome(plasma=None, details=str(exc))

    async def get_alert_bulletins(self) -> AlertsFetchOutcome:
        try:
            payload = await self._fetch_json(self.settings.swpc_alerts_url)
            if isinstance(payload, list):
                alerts = [item for item in payload if isinstance(item, dict)]
                return AlertsFetchOutcome(alerts=alerts)
            raise RuntimeError("Unexpected NOAA alerts payload")
        except Exception as exc:
            return AlertsFetchOutcome(alerts=[], details=str(exc))

    async def get_latest_bz(self) -> MagneticFetchOutcome:
        try:
            payload = await self._fetch_json(self.settings.swpc_mag_url)
            if not isinstance(payload, list) or len(payload) < 2:
                raise RuntimeError("Unexpected magnetic payload")

            for row in reversed(payload[1:]):
                try:
                    observed_at = self._parse_time(str(row[0]))
                    bz_nt = float(row[3])
                    return MagneticFetchOutcome(bz_nt=bz_nt, observed_at=observed_at)
                except Exception:
                    continue

            raise RuntimeError("No valid Bz sample found")
        except Exception as exc:
            return MagneticFetchOutcome(bz_nt=None, observed_at=None, details=str(exc))

    async def _fetch_json(self, url: str) -> list | dict:
        retries = self.settings.request_retries
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            for attempt in range(retries + 1):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.json()
                except Exception as exc:
                    last_error = exc
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"Failed to fetch {url}: {last_error}")

    def _load_mock_observation(self) -> SpaceWeatherObservation:
        with self.mock_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        return SpaceWeatherObservation(
            observed_at=self._parse_time(payload["observed_at"]),
            kp=float(payload["kp"]),
            xray_flux=float(payload["xray_flux"]),
            proton_flux_10mev=float(payload["proton_flux_10mev"]),
            source="mock",
        )

    def _extract_latest_kp(self, payload: list) -> tuple[float, datetime]:
        if not payload or len(payload) < 2:
            raise RuntimeError("Unexpected Kp payload")

        # payload[0] is header row; iterate backwards until a valid data row is found.
        for row in reversed(payload[1:]):
            try:
                return float(row[1]), self._parse_time(str(row[0]))
            except Exception:
                continue
        raise RuntimeError("No valid Kp sample found")

    def _extract_latest_xray(self, payload: list[dict]) -> tuple[float, datetime]:
        candidates = [
            item
            for item in payload
            if str(item.get("energy", "")).strip() == "0.1-0.8nm" and item.get("flux") is not None
        ]
        if not candidates:
            raise RuntimeError("No 0.1-0.8nm xray samples found")
        latest = max(candidates, key=lambda item: self._parse_time(item["time_tag"]))
        return float(latest["flux"]), self._parse_time(latest["time_tag"])

    def _extract_latest_proton_10mev(self, payload: list[dict]) -> tuple[float, datetime]:
        def normalize_energy(value: str) -> str:
            return value.replace(" ", "").lower()

        candidates = [
            item
            for item in payload
            if normalize_energy(str(item.get("energy", ""))) == ">=10mev" and item.get("flux") is not None
        ]
        if not candidates:
            raise RuntimeError("No >=10 MeV proton samples found")
        latest = max(candidates, key=lambda item: self._parse_time(item["time_tag"]))
        return float(latest["flux"]), self._parse_time(latest["time_tag"])

    def _parse_time(self, value: str) -> datetime:
        text = value.strip()
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        if "." in text and " " in text:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f")
            return parsed.replace(tzinfo=timezone.utc)
        if " " in text:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
