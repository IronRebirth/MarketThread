from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertStatus(StrEnum):
    """Persisted lifecycle state for a watchlist alert."""

    NEW = "new"
    SEEN = "seen"
    ACKNOWLEDGED = "acknowledged"


class WatchlistAlertState(BaseModel):
    """Durable interaction state associated with one derived alert."""

    model_config = ConfigDict(frozen=True)

    alert_id: UUID
    watchlist_id: UUID
    watchlist_item_id: UUID
    market_impact_id: UUID
    event_id: UUID
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    seen_at: datetime | None = None
    acknowledged_at: datetime | None = None
