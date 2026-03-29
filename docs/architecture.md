# Architecture Overview

## Goal

Build an automated early warning panel for incoming electromagnetic storm risk using NOAA/SWPC observations.

## High-level components

1. Data Collector (backend/app/clients/swpc_client.py)
- Polls NOAA/SWPC feeds at a fixed interval.
- Retries failed requests.
- Falls back to mock data when live feed is not available.

2. Risk Engine (backend/app/services/risk_engine.py)
- Maps observations to NOAA scales:
  - Geomagnetic: G1-G5 from Kp
  - Radiation: S1-S5 from proton >=10 MeV
  - Radio blackout: R1-R5 from X-ray flux
- Builds a composite risk level and confidence for a 6-24 hour horizon.

3. Alert Service (backend/app/services/alert_service.py)
- Triggers alerts when severity is strong or above.
- Uses dedupe keys and cooldown to prevent noisy duplicates.
- Supports manual test alerts.

4. Notification Service (backend/app/services/email_notifier.py)
- Sends alert emails through SMTP when enabled.

5. API Layer (backend/app/api/routes)
- GET /api/status
- GET /api/alerts
- POST /api/alerts/test
- GET /api/health

6. Dashboard (frontend/src/pages/DashboardPage.tsx)
- Displays live source status, key metrics, component severities, and alert timeline.
- Refreshes automatically.

## Data flow

1. Collector fetches Kp, X-ray, Proton data.
2. Data normalized into a shared observation model.
3. Risk snapshot computed from latest values + short-term trend.
4. Alert service decides if new alert should be created.
5. API exposes latest state.
6. Frontend polls API and renders warning panel.

## Fault tolerance

- Live feed failures do not stop the pipeline.
- Mock fallback keeps the panel operational for demo continuity.
- Source health is reported to UI for operator transparency.
