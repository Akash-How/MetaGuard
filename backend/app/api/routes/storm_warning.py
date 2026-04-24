from fastapi import APIRouter, HTTPException

from app.schemas.modules import StormAlert, StormAlertsResponse, StormSimulationRequest, WatchedAssetsResponse
from app.services.storm_warning import get_storm_warning_service

router = APIRouter()
service = get_storm_warning_service()


@router.get("/alerts", response_model=StormAlertsResponse)
def get_storm_alerts() -> StormAlertsResponse:
    return service.list_alerts()


@router.get("/alert/{alert_id}", response_model=StormAlert)
def get_storm_alert(alert_id: str) -> StormAlert:
    try:
        return service.get_alert(alert_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/simulate", response_model=StormAlert)
def simulate_storm_alert(payload: StormSimulationRequest) -> StormAlert:
    return service.simulate(payload)


@router.get("/watched", response_model=WatchedAssetsResponse)
def get_watched_assets() -> WatchedAssetsResponse:
    return service.watched()
