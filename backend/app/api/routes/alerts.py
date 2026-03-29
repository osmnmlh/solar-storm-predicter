from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import AlertActionRequest, AlertRecord, TestAlertRequest

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertRecord])
async def list_alerts(request: Request, limit: int = Query(default=50, ge=1, le=300)) -> list[AlertRecord]:
    alert_service = request.app.state.alert_service
    return alert_service.list_alerts(limit)


@router.get("/alerts/active", response_model=list[AlertRecord])
async def list_active_alerts(request: Request) -> list[AlertRecord]:
    alert_service = request.app.state.alert_service
    return alert_service.list_active()


@router.post("/alerts/test", response_model=AlertRecord)
async def create_test_alert(request: Request, payload: TestAlertRequest) -> AlertRecord:
    alert_service = request.app.state.alert_service
    notifier = request.app.state.email_notifier

    alert = alert_service.create_manual_alert(
        level=payload.level,
        title=payload.title,
        message=payload.message,
    )
    await notifier.send_alert(alert)
    return alert


@router.post("/alerts/{alert_id}/ack", response_model=AlertRecord)
async def acknowledge_alert(request: Request, alert_id: str, payload: AlertActionRequest) -> AlertRecord:
    alert_service = request.app.state.alert_service
    try:
        return alert_service.acknowledge_alert(alert_id, note=payload.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/alerts/{alert_id}/close", response_model=AlertRecord)
async def close_alert(request: Request, alert_id: str, payload: AlertActionRequest) -> AlertRecord:
    alert_service = request.app.state.alert_service
    try:
        return alert_service.close_alert(alert_id, note=payload.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")
