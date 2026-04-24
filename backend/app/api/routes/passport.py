from fastapi import APIRouter, HTTPException

from app.schemas.modules import DataPassportResponse, PassportMcpRequest, PassportTrustScoreResponse
from app.services.passport import DataPassportService

router = APIRouter()
service = DataPassportService()


@router.post("/mcp")
def passport_mcp(payload: PassportMcpRequest) -> dict[str, str]:
    return service.handle_mcp(payload)


@router.get("/{fqn:path}/trust-score", response_model=PassportTrustScoreResponse)
def get_trust_score(fqn: str) -> PassportTrustScoreResponse:
    try:
        return service.get_trust_score(fqn)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{fqn:path}", response_model=DataPassportResponse)
def get_passport(fqn: str) -> DataPassportResponse:
    try:
        return service.get_passport(fqn)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
