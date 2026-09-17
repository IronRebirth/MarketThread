from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import CompanyImpact, CompanyImpactDirection, ImpactType


class CompanyImpactResponse(BaseModel):
    """Persisted company impact response."""

    model_config = ConfigDict(frozen=True)

    impact_id: UUID
    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    impact_type: ImpactType
    direction: CompanyImpactDirection
    mechanism: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


def to_company_impact_response(
    impact: CompanyImpact,
    impact_id: UUID,
) -> CompanyImpactResponse:
    """Convert a persisted impact into an API response."""

    return CompanyImpactResponse(
        impact_id=impact_id,
        event_id=impact.event_id,
        company_name=impact.company_name,
        ticker=impact.ticker,
        impact_type=impact.impact_type,
        direction=impact.direction,
        mechanism=impact.mechanism,
        confidence=impact.confidence,
        evidence_article_ids=impact.evidence_article_ids,
        rationale=impact.rationale,
    )
