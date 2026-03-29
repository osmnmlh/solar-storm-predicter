from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.schemas import (
    CombinedRiskScenario,
    DonkiSummary,
    ForecastPoint,
    MetricBand,
    RiskSnapshot,
    ScaleLevel,
    SpaceWeatherObservation,
    TrendSignal,
)
from app.services.forecast_service import classify_trend, horizon_factor, linear_slope, trend_boost


def geomagnetic_level_from_kp(kp: float) -> ScaleLevel:
    if kp >= 9.0:
        return ScaleLevel(code="G5", severity=5)
    if kp >= 8.0:
        return ScaleLevel(code="G4", severity=4)
    if kp >= 7.0:
        return ScaleLevel(code="G3", severity=3)
    if kp >= 6.0:
        return ScaleLevel(code="G2", severity=2)
    if kp >= 5.0:
        return ScaleLevel(code="G1", severity=1)
    return ScaleLevel(code="none", severity=0)


def radio_blackout_level_from_xray(flux: float) -> ScaleLevel:
    if flux >= 2e-3:
        return ScaleLevel(code="R5", severity=5)
    if flux >= 1e-3:
        return ScaleLevel(code="R4", severity=4)
    if flux >= 1e-4:
        return ScaleLevel(code="R3", severity=3)
    if flux >= 5e-5:
        return ScaleLevel(code="R2", severity=2)
    if flux >= 1e-5:
        return ScaleLevel(code="R1", severity=1)
    return ScaleLevel(code="none", severity=0)


def radiation_level_from_proton_flux(flux_10mev: float) -> ScaleLevel:
    if flux_10mev >= 1e5:
        return ScaleLevel(code="S5", severity=5)
    if flux_10mev >= 1e4:
        return ScaleLevel(code="S4", severity=4)
    if flux_10mev >= 1e3:
        return ScaleLevel(code="S3", severity=3)
    if flux_10mev >= 1e2:
        return ScaleLevel(code="S2", severity=2)
    if flux_10mev >= 10:
        return ScaleLevel(code="S1", severity=1)
    return ScaleLevel(code="none", severity=0)


def estimate_roti_proxy(*, kp: float, bz_nt: float, speed_kms: float, xray_flux: float) -> float:
    roti = 0.08
    roti += max(0.0, kp - 3.0) * 0.11
    roti += max(0.0, -bz_nt - 2.0) * 0.032
    roti += max(0.0, speed_kms - 450.0) / 500.0

    if xray_flux >= 1e-4:
        roti += 0.45
    elif xray_flux >= 1e-5:
        roti += 0.25
    elif xray_flux >= 1e-6:
        roti += 0.08

    return round(max(0.05, min(5.0, roti)), 3)


def _severity_label(severity: int) -> str:
    mapping = {
        0: "calm",
        1: "minor",
        2: "moderate",
        3: "strong",
        4: "severe",
        5: "extreme",
    }
    return mapping.get(severity, "unknown")


def _clamp_severity(value: int) -> int:
    return max(0, min(5, value))


def _band(metric: str, code: str, label: str, color: str, severity: int, description: str) -> MetricBand:
    return MetricBand(metric=metric, code=code, label=label, color=color, severity=severity, description=description)


def _speed_band(speed_kms: float) -> MetricBand:
    if speed_kms < 450:
        return _band("speed", "speed_nominal", "Nominal", "green", 0, "Sakin gunes ruzgari; manyetosfer dengede")
    if speed_kms < 600:
        return _band(
            "speed",
            "speed_disturbed",
            "Hareketli",
            "yellow",
            1,
            "Koronal delik kaynakli hizli akislar; yuzey sarjlanma riski",
        )
    if speed_kms <= 800:
        return _band(
            "speed",
            "speed_storm",
            "Kritik/Firtina",
            "orange",
            2,
            "CME oncu sok dalgasi; LEO drag belirginlesir",
        )
    return _band(
        "speed",
        "speed_extreme",
        "Ekstrem/Felaket",
        "red",
        3,
        "Siddetli dogrudan CME carpmasi; donanimsal ariza riski",
    )


def _bz_band(bz_nt: float) -> MetricBand:
    if bz_nt >= 0:
        return _band("bz", "bz_closed", "Kapali Kapi", "green", 0, "Manyetik kalkan tam kapasite")
    if bz_nt >= -5:
        return _band("bz", "bz_leakage", "Sizinti", "yellow", 1, "Zayif yeniden baglanma; izleme modu")
    if bz_nt >= -15:
        return _band("bz", "bz_open", "Acik Kapi", "orange", 2, "Kritik enerji enjeksiyonu; G3 riski")
    return _band("bz", "bz_torn", "Yirtik Kalkan", "red", 3, "G4-G5 duzeyinde ciddi manyetik baski")


def _kp_band(kp: float) -> MetricBand:
    if kp <= 3:
        return _band("kp", "kp_nominal", "Kp 0-3", "green", 0, "Sakin/hareketli sinirinda")
    if kp <= 5:
        return _band("kp", "kp_watch", "Kp 4-5", "yellow", 1, "Kalkan baskisi ve G1 siniri")
    if kp <= 7:
        return _band("kp", "kp_storm", "Kp 6-7", "orange", 2, "G2-G3 kritik esik; drag ve GPS sapmasi")
    return _band("kp", "kp_extreme", "Kp 8-9", "red", 3, "G4-G5 siddetli/ekstrem firtina")


def _proton_band(proton_flux_10mev: float) -> MetricBand:
    if proton_flux_10mev < 10:
        return _band("proton", "p_below_s1", "Below S1", "green", 0, "Parcacik riski dusuk")
    if proton_flux_10mev < 1e2:
        return _band("proton", "p_s1", "S1 Minor", "yellow", 1, "Kutup HF haberlesmesinde hafif zayiflama")
    if proton_flux_10mev < 1e3:
        return _band("proton", "p_s2", "S2 Moderate", "yellow", 1, "Goruntuleme gurultusu ve panel verim kaybi")
    if proton_flux_10mev < 1e4:
        return _band("proton", "p_s3", "S3 Strong", "orange", 2, "SEU ve star-tracker korlesmesi riski")
    if proton_flux_10mev < 1e5:
        return _band("proton", "p_s4", "S4 Severe", "red", 3, "Kalici donanim hasari riski yuksek")
    return _band("proton", "p_s5", "S5 Extreme", "red", 3, "Uydu kaybi olasiligi ve islemci hasari")


def _xray_band(xray_flux: float) -> MetricBand:
    if xray_flux < 1e-6:
        return _band("xray", "x_ab", "A/B", "green", 0, "Arka plan seviyesi")
    if xray_flux < 1e-5:
        return _band("xray", "x_c", "C", "yellow", 1, "Minimal radio paraziti")
    if xray_flux < 1e-4:
        return _band("xray", "x_m", "M", "orange", 2, "R1-R2; kutup HF kesintileri")
    return _band("xray", "x_x", "X", "red", 3, "R3-R5; genis capli radio blackout riski")


def _roti_band(roti_tecu_min: float) -> MetricBand:
    if roti_tecu_min < 0.2:
        return _band("roti", "roti_nominal", "ROTI < 0.2", "green", 0, "Iyonosfer stabil")
    if roti_tecu_min < 0.5:
        return _band("roti", "roti_noisy", "0.2-0.5", "yellow", 1, "Hafif scintillation ve cm-level sapmalar")
    if roti_tecu_min < 1.0:
        return _band("roti", "roti_critical", "0.5-1.0", "orange", 2, "Loss-of-lock riski ve anti-spoofing zorlugu")
    return _band("roti", "roti_blackout", "ROTI >= 1.0", "red", 3, "Navigasyon felaketi ve genis sinyal bozulmasi")


def _donki_pressure(donki_summary: DonkiSummary | None) -> int:
    if donki_summary is None or donki_summary.source_status != "live" or donki_summary.event_count == 0:
        return 0

    if donki_summary.max_event_score >= 4.0 or donki_summary.weighted_score >= 12:
        return 2
    if donki_summary.max_event_score >= 2.8 or donki_summary.weighted_score >= 5:
        return 1
    return 0


def _select_core_scenario(speed_band: MetricBand, bz_band: MetricBand, kp_band: MetricBand) -> CombinedRiskScenario:
    if speed_band.severity == 0 and bz_band.severity == 0 and kp_band.severity == 0:
        return CombinedRiskScenario(
            code="nominal-safe",
            name="Nominal / Guvenli Senaryo",
            color="green",
            severity=0,
            analysis="Kapali manyetik kapi ve dusuk momentum; enerji enjeksiyonu yok.",
        )

    if speed_band.severity == 1 and bz_band.severity == 1 and kp_band.severity == 1:
        return CombinedRiskScenario(
            code="shield-pressure",
            name="Kalkan Baskisi",
            color="yellow",
            severity=2,
            analysis="Manyetik kapi aralandi ve ruzgar hizlandi; firtina yaklasimi.",
        )

    if speed_band.severity == 2 and bz_band.severity == 2 and kp_band.severity == 2:
        return CombinedRiskScenario(
            code="energy-injection",
            name="Enerji Enjeksiyonu",
            color="orange",
            severity=3,
            analysis="Kritik esik asildi; yeniden baglanma ile enerji iyonosfere akiyor.",
        )

    if speed_band.severity == 3 and bz_band.severity == 3 and kp_band.severity == 3:
        return CombinedRiskScenario(
            code="system-collapse",
            name="Sistem Cokusu",
            color="red",
            severity=5,
            analysis="Kalkan agir hasarli; G4-G5 seviyesinde genis capli operasyonel kayip riski.",
        )

    core_score = speed_band.severity + bz_band.severity + kp_band.severity
    if core_score <= 2:
        return CombinedRiskScenario(
            code="transitional-watch",
            name="Gecis / Izleme",
            color="yellow",
            severity=1,
            analysis="Metrikler tam hizalanmamis olsa da kalkan baskisi belirtileri var.",
        )
    if core_score <= 5:
        return CombinedRiskScenario(
            code="mixed-storm",
            name="Karisik Firtina Dinamigi",
            color="orange",
            severity=3,
            analysis="Coklu metrikler kritik esiklere yaklasiyor; etkiler sektorel olarak hissedilir.",
        )
    return CombinedRiskScenario(
        code="escalating-collapse",
        name="Yukselen Cokus Riski",
        color="red",
        severity=4,
        analysis="Birden cok ana metrik asiri riskte; altyapi ve uydu riski yuksek.",
    )


def _derive_likely_issues(
    *,
    speed_band: MetricBand,
    bz_band: MetricBand,
    kp_band: MetricBand,
    proton_band: MetricBand,
    xray_band: MetricBand,
    roti_band: MetricBand,
    donki_pressure: int,
) -> list[str]:
    issues: list[str] = []

    if speed_band.severity >= 1:
        issues.append("Manyetik alanda titreşim ve uydu yuzeylerinde statik sarjlanma riski")
    if speed_band.severity >= 2:
        issues.append("LEO uydularinda atmosferik suruklenme (drag) artisi")
    if speed_band.severity >= 3:
        issues.append("Manyetosfer sikismasi ve donanimsal ariza riski")

    if bz_band.severity >= 2:
        issues.append("Manyetik yeniden baglanma ile iyonosfere dogrudan enerji aktarimi")
    if bz_band.severity >= 3:
        issues.append("Enerji iletim hatlarinda GIC ve trafo hasari riski")

    if kp_band.severity >= 1:
        issues.append("GPS konumlamada bozulma ve navigasyon sapmalari")
    if kp_band.severity >= 2:
        issues.append("HF radyo yayiliminda belirgin zayiflama ve kesintiler")
    if kp_band.severity >= 3:
        issues.append("G4-G5 seviyesinde yaygin altyapi bozulum riski")

    if proton_band.code in {"p_s3", "p_s4", "p_s5"}:
        issues.append("Uydu elektroniklerinde SEU ve bellek bit hatalari")
    if proton_band.code in {"p_s4", "p_s5"}:
        issues.append("Uydu gunes panellerinde kalici verim kaybi veya uydu kaybi riski")

    if xray_band.severity >= 2:
        issues.append("Kutup rotalarinda HF radyo kesintileri ve zamanlama bozulmasi")
    if xray_band.severity >= 3:
        issues.append("Gunes goren tarafta genis capli radio blackout")

    if roti_band.severity >= 2:
        issues.append("GNSS loss-of-lock riski ve anti-spoofing kararsizligi")
    if roti_band.severity >= 3:
        issues.append("Otonom sistemlerde navigasyon guvenilirliginin ciddi dusmesi")

    if donki_pressure >= 1:
        issues.append("Dis olay baskisi (CME/FLR/SEP) nedeniyle risk ivmelenmesi")

    # Keep deterministic order and remove duplicates.
    unique: list[str] = []
    for item in issues:
        if item not in unique:
            unique.append(item)
    return unique


def _recommended_actions(
    *,
    scenario: CombinedRiskScenario,
    proton_band: MetricBand,
    xray_band: MetricBand,
    roti_band: MetricBand,
) -> list[str]:
    actions: list[str] = []

    if scenario.color == "green":
        actions.append("Normal operasyon; 5 dakikalik periyodik izleme surdur")
    if scenario.color == "yellow":
        actions.append("Izleme moduna gec; yedek haberlesme kanallari hazirla")
    if scenario.color == "orange":
        actions.append("Uydu guvenli mod hazirligi ve HF/GNSS operasyon kisitlamasi uygula")
    if scenario.color == "red":
        actions.append("Acil durum protokolu: kritik sistemleri izole et ve operasyonu minimuma cek")

    if proton_band.code in {"p_s3", "p_s4", "p_s5"}:
        actions.append("SEU koruma modlarini etkinlestir; bellek scrubbing frekansini artir")

    if xray_band.severity >= 2:
        actions.append("HF bagimliligini azalt; SATCOM veya alternatif linklere gec")

    if roti_band.severity >= 2:
        actions.append("GNSS anti-spoofing esiklerini sikilastir ve inertial fallback etkinlestir")

    unique: list[str] = []
    for item in actions:
        if item not in unique:
            unique.append(item)
    return unique


def _impact_summary(g_level: ScaleLevel, s_level: ScaleLevel, r_level: ScaleLevel) -> list[str]:
    impacts: list[str] = []
    if g_level.severity >= 3:
        impacts.append("Power grid and GNSS disturbances possible at high latitudes")
    if s_level.severity >= 2:
        impacts.append("Increased satellite radiation risk and polar route communication impacts")
    if r_level.severity >= 2:
        impacts.append("HF radio degradation likely on sunlit side")
    if not impacts:
        impacts.append("No major operational impact expected under current conditions")
    return impacts


def _donki_impact_summary(donki_summary: DonkiSummary | None) -> list[str]:
    if donki_summary is None or donki_summary.source_status != "live" or donki_summary.event_count == 0:
        return []

    details = [
        (
            f"NASA DONKI: {donki_summary.lookback_days}d window has "
            f"{donki_summary.event_count} tracked solar events"
        )
    ]
    if donki_summary.top_event:
        details.append(f"Dominant external driver: {donki_summary.top_event}")
    return details


def _build_forecast_timeline(
    *,
    base_severity: int,
    scenario_severity: int,
    donki_pressure: int,
    raw_confidence: float,
    kp_slope: float,
    proton_slope: float,
    xray_slope: float,
) -> list[ForecastPoint]:
    timeline: list[ForecastPoint] = []

    for horizon in (6, 12, 24):
        factor = horizon_factor(horizon)
        trend_pressure = (kp_slope * 0.32) + (proton_slope * 0.22) + (xray_slope * 10500 * 0.46)
        trend_offset = round(trend_pressure * factor)
        scenario_offset = round(scenario_severity * max(0.18, factor * 0.18))
        donki_offset = round(donki_pressure * max(0.4, factor * 0.75))
        predicted_severity = _clamp_severity(base_severity + trend_offset + scenario_offset + donki_offset)

        timeline.append(
            ForecastPoint(
                horizon_hours=horizon,
                predicted_severity=predicted_severity,
                predicted_level=_severity_label(predicted_severity),
                confidence=round(max(0.42, min(0.96, raw_confidence * factor + 0.2)), 2),
            )
        )
    return timeline


def build_risk_snapshot(
    observation: SpaceWeatherObservation,
    recent_observations: Iterable[SpaceWeatherObservation],
    donki_summary: DonkiSummary | None = None,
    plasma_speed_kms: float | None = None,
    bz_nt: float | None = None,
    roti_tecu_min: float | None = None,
) -> RiskSnapshot:
    history = list(recent_observations)

    speed_kms = plasma_speed_kms if plasma_speed_kms is not None else max(300.0, 360.0 + observation.kp * 48.0)
    bz_value = bz_nt if bz_nt is not None else (observation.bz_nt if observation.bz_nt is not None else -3.0)
    roti_value = roti_tecu_min
    if roti_value is None:
        roti_value = observation.roti_tecu_min
    if roti_value is None:
        roti_value = estimate_roti_proxy(
            kp=observation.kp,
            bz_nt=bz_value,
            speed_kms=speed_kms,
            xray_flux=observation.xray_flux,
        )

    speed_band = _speed_band(speed_kms)
    bz_band = _bz_band(bz_value)
    kp_band = _kp_band(observation.kp)
    proton_band = _proton_band(observation.proton_flux_10mev)
    xray_band = _xray_band(observation.xray_flux)
    roti_band = _roti_band(roti_value)

    scenario = _select_core_scenario(speed_band, bz_band, kp_band)
    donki_pressure = _donki_pressure(donki_summary)

    g_level = geomagnetic_level_from_kp(observation.kp)
    s_level = radiation_level_from_proton_flux(observation.proton_flux_10mev)
    r_level = radio_blackout_level_from_xray(observation.xray_flux)

    kp_values = [item.kp for item in history]
    proton_values = [item.proton_flux_10mev for item in history]
    xray_values = [item.xray_flux for item in history]

    kp_trend = classify_trend(kp_values)
    proton_trend = classify_trend(proton_values)
    xray_trend = classify_trend(xray_values)

    kp_slope = linear_slope(kp_values)
    proton_slope = linear_slope(proton_values)
    xray_slope = linear_slope(xray_values)

    kp_boost = trend_boost(kp_values)
    proton_boost = trend_boost(proton_values)
    xray_boost = trend_boost(xray_values)
    combined_boost = max(kp_boost, proton_boost, xray_boost)

    component_weighted_score = (g_level.severity * 0.45) + (s_level.severity * 0.2) + (r_level.severity * 0.35)
    environmental_pressure = (
        speed_band.severity * 0.7
        + bz_band.severity * 0.9
        + kp_band.severity * 1.0
        + proton_band.severity * 0.65
        + xray_band.severity * 0.55
        + roti_band.severity * 0.8
        + donki_pressure * 0.7
    )
    trend_driver_score = max(0.0, (kp_slope * 0.18) + (proton_slope * 0.012) + (xray_slope * 7600))
    composite_score = round(component_weighted_score + environmental_pressure + trend_driver_score, 2)

    base_severity = max(g_level.severity, s_level.severity, r_level.severity, scenario.severity)
    additional = 0
    if proton_band.code in {"p_s4", "p_s5"}:
        additional += 1
    if xray_band.code == "x_x":
        additional += 1
    if roti_band.code == "roti_blackout":
        additional += 1
    projected_severity = _clamp_severity(base_severity + max(0, combined_boost) + donki_pressure + additional)

    confidence = min(
        0.97,
        0.52 + len(history) * 0.018 + (0.03 if bz_nt is not None else 0.0) + (0.02 if plasma_speed_kms is not None else 0.0),
    )

    trends = [
        TrendSignal(metric="kp", trend=kp_trend, slope=round(kp_slope, 4)),
        TrendSignal(metric="proton_flux_10mev", trend=proton_trend, slope=round(proton_slope, 4)),
        TrendSignal(metric="xray_flux", trend=xray_trend, slope=round(xray_slope, 8)),
    ]

    forecast_timeline = _build_forecast_timeline(
        base_severity=projected_severity,
        scenario_severity=scenario.severity,
        donki_pressure=donki_pressure,
        raw_confidence=confidence,
        kp_slope=kp_slope,
        proton_slope=proton_slope,
        xray_slope=xray_slope,
    )

    likely_issues = _derive_likely_issues(
        speed_band=speed_band,
        bz_band=bz_band,
        kp_band=kp_band,
        proton_band=proton_band,
        xray_band=xray_band,
        roti_band=roti_band,
        donki_pressure=donki_pressure,
    )
    recommended_actions = _recommended_actions(
        scenario=scenario,
        proton_band=proton_band,
        xray_band=xray_band,
        roti_band=roti_band,
    )

    combination_signature = "|".join(
        [speed_band.code, bz_band.code, kp_band.code, proton_band.code, xray_band.code, roti_band.code]
    )

    explanation = (
        "Zenith birlesik karar modeli Speed + (-Bz) + Kp cekirdegini Proton, X-ray ve ROTI ile zenginlestirir. "
        f"Scenario={scenario.code}; Speed={speed_band.label}; Bz={bz_band.label}; Kp={kp_band.label}; "
        f"Proton={proton_band.label}; Xray={xray_band.label}; ROTI={roti_band.label}."
    )

    impacts = _impact_summary(g_level, s_level, r_level)
    impacts.extend(_donki_impact_summary(donki_summary))
    for item in likely_issues:
        if item not in impacts:
            impacts.append(item)

    driver_scores = {
        "geomagnetic": round(g_level.severity * 0.45, 2),
        "solar_radiation": round(s_level.severity * 0.2, 2),
        "radio_blackout": round(r_level.severity * 0.35, 2),
        "speed": float(speed_band.severity),
        "bz": float(bz_band.severity),
        "kp": float(kp_band.severity),
        "proton": float(proton_band.severity),
        "xray": float(xray_band.severity),
        "roti": float(roti_band.severity),
        "trend": round(trend_driver_score, 2),
        "donki": float(donki_pressure),
    }

    return RiskSnapshot(
        generated_at=datetime.now(timezone.utc),
        overall_level=_severity_label(projected_severity),
        overall_severity=projected_severity,
        composite_score=composite_score,
        event_pressure=float(donki_pressure),
        confidence=round(confidence, 2),
        geomagnetic=g_level,
        solar_radiation=s_level,
        radio_blackout=r_level,
        driver_scores=driver_scores,
        speed_band=speed_band,
        bz_band=bz_band,
        kp_band=kp_band,
        proton_band=proton_band,
        xray_band=xray_band,
        roti_band=roti_band,
        combined_scenario=scenario,
        combination_signature=combination_signature,
        likely_issues=likely_issues,
        recommended_actions=recommended_actions,
        trends=trends,
        forecast_timeline=forecast_timeline,
        impact_summary=impacts,
        explanation=explanation,
    )
