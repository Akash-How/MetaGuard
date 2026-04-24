from fastapi import APIRouter, HTTPException

from app.schemas.modules import BlastRadiusReport, RiskScoreResponse
from app.services.blast_radius import BlastRadiusService

router = APIRouter()
service = BlastRadiusService()


@router.get("/table/{fqn:path}", response_model=BlastRadiusReport)
def get_blast_radius_for_table(fqn: str) -> BlastRadiusReport:
    try:
        return service.get_table_report(fqn)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/column/{fqn:path}/{column}", response_model=BlastRadiusReport)
def get_blast_radius_for_column(fqn: str, column: str) -> BlastRadiusReport:
    try:
        return service.get_column_report(fqn, column)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/risk-score/{fqn:path}", response_model=RiskScoreResponse)
def get_blast_risk_score(fqn: str) -> RiskScoreResponse:
    try:
        return service.get_risk_score(fqn)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
