from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.company_impact.models import CompanyImpactDirection, ImpactType
from app.events.models import MarketEvent
from app.market_impact.models import ImpactFactor, TimeHorizon
from app.portfolio.models import Portfolio, PortfolioPosition


EventSensitivityQuality = Literal[
    "sufficient",
    "partial",
    "none",
    "empty",
]


class PortfolioEventSensitivityItem(BaseModel):
    """One persisted market impact linked to a current portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
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

    event_type: str
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1)
    catalyst: str
    market_relevance: str
    event_impact_direction: str

    affected_entities: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    first_seen_at: datetime
    last_seen_at: datetime
    event_confidence: float = Field(ge=0.0, le=1.0)

    source_article_ids: tuple[UUID, ...]
    rationale: str = Field(min_length=1)


class PortfolioEventSensitivity(BaseModel):
    """Quality-aware sensitivity of a portfolio to persisted market events."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime

    position_count: int = Field(ge=0)
    matched_position_count: int = Field(ge=0)
    unmatched_position_count: int = Field(ge=0)

    event_count: int = Field(ge=0)
    impact_count: int = Field(ge=0)
    returned_impact_count: int = Field(ge=0)

    quality: EventSensitivityQuality
    unmatched_symbols: tuple[str, ...]
    methodology: str
    notes: tuple[str, ...]
    items: tuple[PortfolioEventSensitivityItem, ...]