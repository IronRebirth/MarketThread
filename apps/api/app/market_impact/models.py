from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.company_impact.models import CompanyImpactDirection, ImpactType


class ImpactFactor(StrEnum):
    """Economic factor through which an event may affect a company."""

    DEMAND = "demand"
    REVENUE = "revenue"
    INPUT_COSTS = "input_costs"
    FINANCING = "financing"
    VALUATION = "valuation"
    SUPPLY_CHAIN = "supply_chain"
    MARKET_ACCESS = "market_access"
    REGULATORY_BURDEN = "regulatory_burden"
    COMPETITIVE_POSITION = "competitive_position"
    OPERATING_RISK = "operating_risk"
    INVESTOR_SENTIMENT = "investor_sentiment"
    OTHER = "other"


class TimeHorizon(StrEnum):
    """Expected time horizon over which an impact may develop."""

    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    UNCERTAIN = "uncertain"


class MarketImpact(BaseModel):
    """Economic market impact associated with a company exposure."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    impact_type: ImpactType
    direction: CompanyImpactDirection
    factor: ImpactFactor
    time_horizon: TimeHorizon
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_article_ids: tuple[UUID, ...] = ()
    rationale: str = Field(min_length=1)
