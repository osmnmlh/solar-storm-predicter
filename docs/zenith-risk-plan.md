# Zenith Combined Risk Model and Ingestion Plan

## 1) Combined Risk Logic (All Metric Combinations)

The panel evaluates all combinations of these metric bands:

- Speed band: `<450`, `450-600`, `600-800`, `>800`
- Bz band: `>=0`, `0..-5`, `-5..-15`, `<-15`
- Kp band: `<=3`, `4-5`, `6-7`, `8-9`
- Proton band: `<10`, `S1`, `S2`, `S3`, `S4/S5`
- X-ray band: `A/B`, `C`, `M`, `X`
- ROTI band: `<0.2`, `0.2-0.5`, `0.5-1.0`, `>=1.0`

Each incoming telemetry sample is mapped to one band per metric.
Then a deterministic mapping computes:

1. Core scenario from `Speed + Bz + Kp`
2. Additional pressure from `Proton + X-ray + ROTI + DONKI`
3. Likely issues list (sector impacts)
4. Recommended action list

This guarantees every possible metric combination maps to one scenario and one impact/action set.

## 2) Core Scenario Mapping

- `nominal-safe` (Green): speed nominal + Bz closed + Kp nominal
- `shield-pressure` (Yellow): speed disturbed + Bz leakage + Kp watch
- `energy-injection` (Orange): speed storm + Bz open + Kp storm
- `system-collapse` (Red): speed extreme + Bz torn + Kp extreme
- Mixed combinations are mapped by weighted core score to:
  - `transitional-watch` (Yellow)
  - `mixed-storm` (Orange)
  - `escalating-collapse` (Red)

## 3) Impact Mapping Rules

Likely issues are added by triggered metric bands, for example:

- Speed storm/extreme -> atmospheric drag, magnetosphere compression
- Bz open/torn -> reconnection, GIC and transformer risk
- Kp 6+ -> GNSS drift, HF degradation, infrastructure pressure
- Proton S3+ -> SEU, memory upset, possible hardware damage
- X-ray M/X -> HF blackout, navigation timing anomalies
- ROTI 0.5+ -> loss-of-lock and anti-spoofing instability

## 4) Data Ingestion and Database Persistence Plan

Data source plan is exposed by API: `GET /api/ingestion/plan`.

Current default schedule and storage target (`telemetry_snapshots`):

- NOAA SWPC plasma (speed+density): every 5 min
- NOAA SWPC magnetic (Bz): every 5 min
- NOAA planetary Kp: every 5 min
- NOAA GOES X-ray: every 5 min
- NOAA GOES proton flux: every 5 min
- NOAA alerts bulletin: every 5 min
- NASA DONKI events: every 15 min (cached)
- ROTI: external provider every 5 min when configured, otherwise model-derived proxy every 5 min

Collector snapshots are persisted to SQLite:

- DB file: `backend/data/space_weather.sqlite3`
- Table: `telemetry_snapshots`
- API stats: `GET /api/storage/stats`
- API recent rows: `GET /api/storage/recent?limit=...`

## 5) Operational Notes

- If external ROTI feed is unavailable, a deterministic ROTI proxy is derived from Kp, Bz, speed, and X-ray.
- NOAA bulletin intelligence keeps incremental memory:
  - memory file: `backend/son_islenen_tarih.txt`
  - report file: `backend/firtina_raporu.txt`
