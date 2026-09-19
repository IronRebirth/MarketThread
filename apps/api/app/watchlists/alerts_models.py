from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WatchlistAlertsQuality = str


class WatchlistAlert(BaseModel):
    """One evidence-backed intelligence alert for a watched instrument."""

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

    event_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1)

    catalyst: str = Field(min_length=1, max_length=64)
    market_relevance: str = Field(min_length=1, max_length=32)
    event_impact_direction: str = Field(min_length=1, max_length=32)

    impact_type: str = Field(min_length=1, max_length=32)
    direction: str = Field(min_length=1, max_length=32)
    factor: str = Field(min_length=1, max_length=64)
    time_horizon: str = Field(min_length=1, max_length=32)

    confidence: float = Field(ge=0.0, le=1.0)
    event_confidence: float = Field(ge=0.0, le=1.0)

    watchlist_item_added_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime

    source_article_ids: tuple[UUID, ...]
    rationale: str = Field(min_length=1)

    explanation: str = Field(min_length=1)


class WatchlistAlerts(BaseModel):
    """Quality-aware derived intelligence alerts for a watchlist."""

    model_config = ConfigDict(frozen=True)

    watchlist_id: UUID
    assessed_at: datetime

    item_count: int = Field(ge=0)
    matched_item_count: int = Field(ge=0)
    unmatched_item_count: int = Field(ge=0)

    alert_count: int = Field(ge=0)
    returned_alert_count: int = Field(ge=0)

    quality: WatchlistAlertsQuality

    alerts: tuple[WatchlistAlert, ...]

    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
