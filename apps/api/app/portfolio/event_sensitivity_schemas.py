from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.company_impact.models import CompanyImpactDirection, ImpactType
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance
from app.market_impact.models import ImpactFactor, TimeHorizon
from app.portfolio.schemas import PortfolioPositionResponse, PortfolioResponse

from .event_sensitivity_models import EventSensitivityQuality


class PortfolioEventSensitivityItemResponse(BaseModel):
    """API representation of one portfolio event-sensitivity item."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPositionResponse

    market_impact_id: UUID
    company_impact_id: UUID
    event_id: UUID

    company_name: str = Field(min_length=1, max_length=255)
    ticker: str = Field(min_length=1, max_length=32)

    impact_type: ImpactType
    direction: CompanyImpactDirection
    factor: ImpactFactor
    time_horizon: TimeHorizon
    confidence: float = Field(ge=0.0, le=1.0)

    event_type: EventType
    title: str = Field(min_length=1, max_length=500)
    summary: str
    catalyst: EventCatalyst
    market_relevance: MarketRelevance
    event_impact_direction: ImpactDirection

    affected_entities: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    first_seen_at: datetime
    last_seen_at: datetime
    event_confidence: float = Field(ge=0.0, le=1.0)

    source_article_ids: tuple[UUID, ...]
    rationale: str


class PortfolioEventSensitivityResponse(BaseModel):
    """API representation of portfolio event sensitivity."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime

    position_count: int
    matched_position_count: int
    unmatched_position_count: int

    event_count: int
    impact_count: int
    returned_impact_count: int

    quality: EventSensitivityQuality
    unmatched_symbols: tuple[str, ...]
    methodology: str
    notes: tuple[str, ...]

    items: tuple[PortfolioEventSensitivityItemResponse, ...]