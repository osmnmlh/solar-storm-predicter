from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import DonkiEvent, DonkiSummary, SpaceWeatherObservation
from app.services.risk_engine import (
    build_risk_snapshot,
    geomagnetic_level_from_kp,
    radiation_level_from_proton_flux,
    radio_blackout_level_from_xray,
)


def _obs(*, kp: float, xray: float, proton: float) -> SpaceWeatherObservation:
    return SpaceWeatherObservation(
        observed_at=datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc),
        kp=kp,
        xray_flux=xray,
        proton_flux_10mev=proton,
        source="live",
    )


def test_geomagnetic_thresholds() -> None:
    assert geomagnetic_level_from_kp(4.9).code == "none"
    assert geomagnetic_level_from_kp(5.0).code == "G1"
    assert geomagnetic_level_from_kp(7.0).code == "G3"
    assert geomagnetic_level_from_kp(9.0).code == "G5"


def test_radiation_thresholds() -> None:
    assert radiation_level_from_proton_flux(8).code == "none"
    assert radiation_level_from_proton_flux(10).code == "S1"
    assert radiation_level_from_proton_flux(150).code == "S2"
    assert radiation_level_from_proton_flux(100000).code == "S5"


def test_radio_blackout_thresholds() -> None:
    assert radio_blackout_level_from_xray(9.5e-6).code == "none"
    assert radio_blackout_level_from_xray(1e-5).code == "R1"
    assert radio_blackout_level_from_xray(1.2e-4).code == "R3"


def test_build_snapshot_with_rising_trend() -> None:
    history = [
        _obs(kp=4.2, xray=7e-6, proton=6),
        _obs(kp=5.2, xray=2e-5, proton=20),
        _obs(kp=6.1, xray=8e-5, proton=130),
    ]
    latest = _obs(kp=6.4, xray=1.4e-4, proton=240)

    snapshot = build_risk_snapshot(latest, [*history, latest])

    assert snapshot.geomagnetic.code == "G2"
    assert snapshot.solar_radiation.code == "S2"
    assert snapshot.radio_blackout.code == "R3"
    assert snapshot.overall_severity >= 3
    assert snapshot.composite_score >= 0
    assert snapshot.horizon_start_hours == 6
    assert snapshot.horizon_end_hours == 24
    assert len(snapshot.forecast_timeline) == 3
    assert snapshot.forecast_timeline[0].horizon_hours == 6


def test_donki_pressure_can_raise_projection() -> None:
    latest = _obs(kp=4.1, xray=8e-6, proton=8.5)
    history = [
        _obs(kp=3.9, xray=7e-6, proton=7.8),
        _obs(kp=4.0, xray=7.5e-6, proton=8.1),
        latest,
    ]

    without_donki = build_risk_snapshot(latest, history)

    donki = DonkiSummary(
        retrieved_at=datetime(2026, 3, 28, 20, 0, tzinfo=timezone.utc),
        source_status="live",
        lookback_days=3,
        event_count=2,
        weighted_score=14.0,
        max_event_score=4.4,
        top_event="FLR: X1.1 flare",
        events=[
            DonkiEvent(
                event_id="FLR-1",
                event_type="FLR",
                started_at=datetime(2026, 3, 28, 17, 0, tzinfo=timezone.utc),
                score=4.4,
                summary="X1.1 flare",
            )
        ],
    )

    with_donki = build_risk_snapshot(latest, history, donki_summary=donki)

    assert with_donki.event_pressure >= 1
    assert with_donki.overall_severity >= without_donki.overall_severity
    assert with_donki.composite_score >= without_donki.composite_score


def test_combination_mapping_energy_injection_scenario() -> None:
    latest = _obs(kp=6.6, xray=4.5e-5, proton=1200)
    history = [
        _obs(kp=5.4, xray=2e-5, proton=450),
        _obs(kp=6.1, xray=3e-5, proton=700),
        latest,
    ]

    snapshot = build_risk_snapshot(
        latest,
        history,
        plasma_speed_kms=710,
        bz_nt=-9.0,
        roti_tecu_min=0.7,
    )

    assert snapshot.combined_scenario is not None
    assert snapshot.combined_scenario.code == "energy-injection"
    assert snapshot.combined_scenario.color == "orange"
    assert snapshot.speed_band is not None and snapshot.speed_band.color == "orange"
    assert snapshot.bz_band is not None and snapshot.bz_band.color == "orange"
    assert snapshot.kp_band is not None and snapshot.kp_band.color == "orange"
    assert any("drag" in issue.lower() for issue in snapshot.likely_issues)


def test_combination_mapping_system_collapse_scenario() -> None:
    latest = _obs(kp=8.7, xray=1.3e-4, proton=25000)
    history = [
        _obs(kp=7.4, xray=8e-5, proton=8000),
        _obs(kp=8.1, xray=1.1e-4, proton=14000),
        latest,
    ]

    snapshot = build_risk_snapshot(
        latest,
        history,
        plasma_speed_kms=920,
        bz_nt=-22.0,
        roti_tecu_min=1.4,
    )

    assert snapshot.combined_scenario is not None
    assert snapshot.combined_scenario.code == "system-collapse"
    assert snapshot.combined_scenario.color == "red"
    assert snapshot.overall_severity >= 4
    assert any("blackout" in issue.lower() for issue in snapshot.likely_issues)
