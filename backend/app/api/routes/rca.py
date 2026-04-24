from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.modules import ExplanationResponse
from app.services.explanation import ExplanationService, get_explanation_service

router = APIRouter()


@router.get("/explain/{fqn}", response_model=ExplanationResponse)
async def get_explanation(
    fqn: str, service: ExplanationService = Depends(get_explanation_service)
) -> ExplanationResponse:
    try:
        return await service.explain(fqn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
