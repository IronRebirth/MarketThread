from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WatchlistNotification(BaseModel):
    """One durable in-app notification for a matched watchlist alert."""

    model_config = ConfigDict(frozen=True)

    notification_id: UUID
    user_id: UUID
    watchlist_id: UUID
    alert_rule_id: UUID
    alert_id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    rule_name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1)
    event_type: str = Field(min_length=1, max_length=64)
    direction: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    read_at: datetime | None = None
