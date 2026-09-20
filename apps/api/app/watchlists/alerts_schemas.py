from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.watchlists.alert_state_models import AlertStatus


class WatchlistAlertResponse(BaseModel):
    """API representation of one watchlist intelligence alert."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: UUID
    watchlist_id: UUID
    watchlist_item_id: UUID
    instrument_id: UUID
    symbol: str
    company_name: str
    ticker: str
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
    confidence: float
    event_confidence: float
    watchlist_item_added_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    source_article_ids: tuple[UUID, ...]
    rationale: str
    explanation: str
    status: AlertStatus
    seen_at: datetime | None
    acknowledged_at: datetime | None


class WatchlistAlertsResponse(BaseModel):
    """API representation of a watchlist alert analysis."""

    watchlist_id: UUID
    assessed_at: datetime
    item_count: int = Field(ge=0)
    matched_item_count: int = Field(ge=0)
    unmatched_item_count: int = Field(ge=0)
    alert_count: int = Field(ge=0)
    returned_alert_count: int = Field(ge=0)
    quality: str
    alerts: tuple[WatchlistAlertResponse, ...]
    methodology: str
    notes: tuple[str, ...]


class WatchlistAlertStateUpdateRequest(BaseModel):
    """Request to advance a watchlist alert lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    status: AlertStatus


class WatchlistAlertStateResponse(BaseModel):
    """API representation of persisted alert interaction state."""

    alert_id: UUID
    watchlist_id: UUID
    watchlist_item_id: UUID
    market_impact_id: UUID
    event_id: UUID
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    seen_at: datetime | None
    acknowledged_at: datetime | None
