# Space Weather Early Warning Panel

Space Weather Early Warning Panel is a FastAPI + React hackathon prototype that monitors NOAA/SWPC signals, enriches predictions with NASA DONKI events, and produces automated 6-24 hour risk alerts for geomagnetic activity.

## Current capabilities

- Live data ingestion from NOAA/SWPC endpoints:
  - Planetary K-index
   - Interplanetary magnetic field Bz
  - GOES X-ray Flux (0.1-0.8nm)
  - GOES Proton Flux (>=10 MeV)
   - Solar wind plasma stream (speed + density)
   - NOAA alerts bulletin stream
- NASA DONKI event intelligence layer (CME, FLR, SEP, GST, MPC, RBE)
- Combined Zenith risk mapping for all metric combinations:
   - Speed + Bz + Kp (core scenario)
   - Proton + X-ray + ROTI (+ DONKI pressure) as amplifiers
- Automatic fallback to mock data when live feed is unavailable
- Rule-based NOAA G/S/R severity mapping
- Composite risk generation for a 6-24 hour warning horizon with external event pressure
- ROTI proxy generation when external ROTI API is unavailable
- Regex-based important NOAA bulletin detection (Kp/G-scale/X-ray/Type II-IV radio)
- Gemini-assisted technical impact extraction for important bulletins
- Persistent NOAA alert memory and report files for incremental processing
- SQLite telemetry persistence for historical risk forensics
- Alert engine with deduplication and cooldown
- Optional SMTP alert delivery
- React dashboard with live status, advanced severity analytics, DONKI pulse charts, and alert lifecycle controls
- Docker Compose local run setup (backend, frontend, MailHog)

## Project layout

- backend: FastAPI API, data collector, rule engine, alert engine, tests
- frontend: React dashboard
- infra: Docker Compose and cloud deployment stubs
- docs: architecture and submission materials

## Local run (without Docker)

### Backend

1. Open terminal in backend
2. Create a virtual environment
3. Install dependencies:

   pip install -r requirements.txt

4. Run API:

   uvicorn app.main:app --reload --port 8000

### Frontend

1. Open another terminal in frontend
2. Install dependencies:

   npm install

3. Run dashboard:

   npm run dev

Dashboard: http://localhost:5173
API: http://localhost:8000/api/status

## Local run (Docker Compose)

1. Open terminal in infra
2. Start stack:

   docker compose up --build

Services:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- MailHog UI: http://localhost:8025

## Environment notes

- backend/.env.example contains backend defaults.
- frontend/.env.example contains Vite API base URL.
- To enable email alerts, set EMAIL_ENABLED=true and SMTP settings.
- To enable DONKI enrichment, set DONKI_API_KEY in backend environment.
- To enable Gemini bulletin analysis, set GEMINI_API_KEY in backend environment.
- NOAA alert memory file and report file are configurable via NOAA_ALERT_MEMORY_FILE and NOAA_ALERT_REPORT_FILE.
- FRONTEND_ORIGIN accepts a comma-separated list (example already provided in backend/.env.example).

## Additional API endpoints

- GET /api/plasma/history
- GET /api/alerts/intel
- GET /api/events/donki
- GET /api/ingestion/plan
- GET /api/storage/stats
- GET /api/storage/recent
- GET /api/status

## Tests

From backend folder:

pytest

## Notes for hackathon demo

- Collector fetch cadence defaults to 5 minutes for core feeds and 15 minutes for DONKI (cached).
- Severity charts use fast-retry polling when first snapshot is not ready, then return to normal frontend refresh.
- DONKI chart shows event count and weighted pressure used in risk model.
- You can test alert lifecycle from dashboard: trigger test alert -> acknowledge -> close.
- Detailed combination matrix and ingestion strategy documentation: docs/zenith-risk-plan.md
