from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WatchlistAlertResponse(BaseModel):
    """API representation of one watchlist intelligence alert."""

    model_config = ConfigDict(frozen=True)

    alert_id: UUID

    watchlist_id: UUID
    watchlist_item_id: UUID
    instrument_id: UUID

    symbol: str = Field(min_length=1, max_length=32)
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str = Field(min_length=1, max_length=32)

    market_impact_id: UUID
    company_impact_id: UUID
    event_id: UUID

    event_type: str
    title: str
    summary: str

    catalyst: str
    market_relevance: str
    event_impact_direction: str

    impact_type: str
    direction: str
    factor: str
    time_horizon: str

    confidence: float = Field(ge=0.0, le=1.0)
    event_confidence: float = Field(ge=0.0, le=1.0)

    watchlist_item_added_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime

    source_article_ids: tuple[UUID, ...]
    rationale: str
    explanation: str


class WatchlistAlertsResponse(BaseModel):
    """API representation of a watchlist's derived intelligence alerts."""

    model_config = ConfigDict(frozen=True)

    watchlist_id: UUID
    assessed_at: datetime

    item_count: int = Field(ge=0)
    matched_item_count: int = Field(ge=0)
    unmatched_item_count: int = Field(ge=0)

    alert_count: int = Field(ge=0)
    returned_alert_count: int = Field(ge=0)

    quality: str
    alerts: tuple[WatchlistAlertResponse, ...]

    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
