from app.schemas.modules import DataPassportResponse, PassportMcpRequest, PassportTrustScoreResponse
from app.services.passport_support import get_passport_support_service
from app.services.impact import get_impact_scorer


class DataPassportService:
    def __init__(self) -> None:
        self.support = get_passport_support_service()

    def get_passport(self, fqn: str) -> DataPassportResponse:
        cached = self.support.cache_get(fqn)
        if cached is not None:
            return DataPassportResponse(**cached, cached=True)
        metadata = self.support.aggregate_metadata(fqn)
        trust_score = self.support.calculate_trust_score(metadata)
        sections = self.support.generate_sections(fqn, metadata)
        impact_score, impact_reason = get_impact_scorer().calculate(fqn)
        payload = {
            "fqn": fqn,
            "trust_score": trust_score.model_dump(),
            "summary": sections["plain_english_summary"],
            "sections": sections,
            "metadata": metadata.model_dump(),
            "impact_score": impact_score,
            "impact_reason": impact_reason,
        }
        self.support.cache_set(fqn, payload)
        return DataPassportResponse(**payload, cached=False)

    def get_trust_score(self, fqn: str) -> PassportTrustScoreResponse:
        metadata = self.support.aggregate_metadata(fqn)
        return PassportTrustScoreResponse(
            fqn=fqn,
            trust_score=self.support.calculate_trust_score(metadata),
        )

    def handle_mcp(self, payload: PassportMcpRequest) -> dict[str, str]:
        passport = self.get_passport(payload.fqn)
        return {"question": payload.question, "fqn": payload.fqn, "answer": passport.summary}
