from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from app.schemas import (
    DonkiSummary,
    NoaaAlertIntelSummary,
    PipelineStats,
    PlasmaSnapshot,
    RiskSnapshot,
    SourceHealth,
    SpaceWeatherObservation,
)


@dataclass
class RuntimeState:
    latest_observation: SpaceWeatherObservation | None = None
    latest_plasma: PlasmaSnapshot | None = None
    risk_snapshot: RiskSnapshot | None = None
    donki_summary: DonkiSummary | None = None
    noaa_alert_intel: NoaaAlertIntelSummary | None = None
    source_health: SourceHealth = field(default_factory=SourceHealth)
    pipeline_stats: PipelineStats = field(default_factory=PipelineStats)
    recent_observations: deque[SpaceWeatherObservation] = field(default_factory=lambda: deque(maxlen=288))
    recent_plasma: deque[PlasmaSnapshot] = field(default_factory=lambda: deque(maxlen=288))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
