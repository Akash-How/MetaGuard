from fastapi import APIRouter, HTTPException

from app.schemas.modules import (
    DeadDataActionResponse,
    DeadDataAssetDetail,
    DeadDataScanResponse,
    DeadDataSummaryResponse,
    DeadDataValidationResponse,
)
from app.services.dead_data import DeadDataService

router = APIRouter()
service = DeadDataService()


@router.get("/scan", response_model=DeadDataScanResponse)
def scan_dead_data() -> DeadDataScanResponse:
    return service.scan()


@router.get("/asset/{fqn:path}", response_model=DeadDataAssetDetail)
def get_dead_data_asset(fqn: str) -> DeadDataAssetDetail:
    try:
        return service.get_asset_detail(fqn)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/validate/{fqn:path}", response_model=DeadDataValidationResponse)
def validate_dead_data_asset(fqn: str) -> DeadDataValidationResponse:
    return service.validate(fqn)


@router.post("/remove/{fqn:path}", response_model=DeadDataActionResponse)
def remove_dead_data_asset(fqn: str) -> DeadDataActionResponse:
    try:
        return DeadDataActionResponse(**service.mark_removed(fqn))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review/{fqn:path}", response_model=DeadDataActionResponse)
def review_dead_data_asset(fqn: str) -> DeadDataActionResponse:
    return DeadDataActionResponse(**service.mark_reviewed(fqn))


@router.get("/summary", response_model=DeadDataSummaryResponse)
def get_dead_data_summary() -> DeadDataSummaryResponse:
    return service.get_summary()
