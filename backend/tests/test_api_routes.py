from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.clients.swpc_client import AlertsFetchOutcome, FetchOutcome, MagneticFetchOutcome, PlasmaFetchOutcome
from app.main import create_app
from app.schemas import PlasmaSnapshot, SpaceWeatherObservation


class FakeSWPCClient:
    async def get_latest_observation(self) -> FetchOutcome:
        return FetchOutcome(
            observation=SpaceWeatherObservation(
                observed_at=datetime.now(timezone.utc),
                kp=5.2,
                xray_flux=2e-5,
                proton_flux_10mev=18.0,
                source="mock",
            ),
            used_mock=True,
            details="test client",
        )

    async def get_latest_plasma(self) -> PlasmaFetchOutcome:
        return PlasmaFetchOutcome(
            plasma=PlasmaSnapshot(
                observed_at=datetime.now(timezone.utc),
                density_pcm3=7.4,
                speed_kms=455.0,
                speed_status="normal",
                source="mock",
            )
        )

    async def get_alert_bulletins(self) -> AlertsFetchOutcome:
        return AlertsFetchOutcome(alerts=[])

    async def get_latest_bz(self) -> MagneticFetchOutcome:
        return MagneticFetchOutcome(bz_nt=-4.2, observed_at=datetime.now(timezone.utc))


app = create_app()
app.state.swpc_client = FakeSWPCClient()
client = TestClient(app)


def test_health_and_status_endpoints() -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json().get("status") == "ok"

    status = client.get("/api/status")
    assert status.status_code == 200
    payload = status.json()
    assert "source_health" in payload
    assert "pipeline_stats" in payload
    assert "latest_plasma" in payload
    assert "donki_summary" in payload
    assert "noaa_alert_intel" in payload


def test_history_and_forecast_endpoints() -> None:
    history = client.get("/api/history?limit=24")
    assert history.status_code == 200
    assert "points" in history.json()
    assert "window_hours" in history.json()

    forecast = client.get("/api/forecast")
    assert forecast.status_code == 200

    plasma_history = client.get("/api/plasma/history?limit=24")
    assert plasma_history.status_code == 200
    assert "points" in plasma_history.json()
    assert "window_hours" in plasma_history.json()

    donki = client.get("/api/events/donki")
    assert donki.status_code == 200
    assert "source_status" in donki.json()

    intel = client.get("/api/alerts/intel")
    assert intel.status_code == 200
    assert "source_status" in intel.json()

    ingestion_plan = client.get("/api/ingestion/plan")
    assert ingestion_plan.status_code == 200
    assert "items" in ingestion_plan.json()

    storage_stats = client.get("/api/storage/stats")
    assert storage_stats.status_code == 200
    assert "total_snapshots" in storage_stats.json()

    storage_recent = client.get("/api/storage/recent?limit=10")
    assert storage_recent.status_code == 200


def test_alert_lifecycle_endpoints() -> None:
    created = client.post(
        "/api/alerts/test",
        json={"level": "strong", "title": "api test", "message": "trigger"},
    )
    assert created.status_code == 200
    alert_id = created.json()["id"]

    ack = client.post(f"/api/alerts/{alert_id}/ack", json={"note": "seen"})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    close = client.post(f"/api/alerts/{alert_id}/close", json={"note": "done"})
    assert close.status_code == 200
    assert close.json()["status"] == "closed"
