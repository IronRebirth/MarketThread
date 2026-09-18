from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    CompanyImpactDirection,
    ImpactFactor,
    ImpactType,
    MarketImpact,
    TimeHorizon,
)


class MarketImpactResponse(BaseModel):
    """Persisted market impact response."""

    model_config = ConfigDict(frozen=True)

    impact_id: UUID
    company_impact_id: UUID
    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    impact_type: ImpactType
    direction: CompanyImpactDirection
    factor: ImpactFactor
    time_horizon: TimeHorizon
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


def to_market_impact_response(
    impact: MarketImpact,
    impact_id: UUID,
    company_impact_id: UUID,
) -> MarketImpactResponse:
    """Convert a persisted market impact into an API response."""

    return MarketImpactResponse(
        impact_id=impact_id,
        company_impact_id=company_impact_id,
        event_id=impact.event_id,
        company_name=impact.company_name,
        ticker=impact.ticker,
        impact_type=impact.impact_type,
        direction=impact.direction,
        factor=impact.factor,
        time_horizon=impact.time_horizon,
        confidence=impact.confidence,
        evidence_article_ids=impact.evidence_article_ids,
        rationale=impact.rationale,
    )
