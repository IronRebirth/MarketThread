from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WatchlistNotificationResponse(BaseModel):
    """API representation of one in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    watchlist_id: UUID
    alert_rule_id: UUID
    alert_id: UUID
    symbol: str
    rule_name: str
    title: str
    message: str
    event_type: str
    direction: str
    confidence: float
    created_at: datetime
    read_at: datetime | None


class WatchlistNotificationsResponse(BaseModel):
    """API representation of the authenticated user's notification inbox."""

    notifications: tuple[WatchlistNotificationResponse, ...]
    returned_count: int = Field(ge=0)
    unread_count: int = Field(ge=0)


class WatchlistNotificationSyncResponse(BaseModel):
    """Result of idempotently materializing matched alert notifications."""

    created_count: int = Field(ge=0)
    existing_count: int = Field(ge=0)
    matched_alert_count: int = Field(ge=0)


class WatchlistNotificationReadResponse(BaseModel):
    """API representation after marking one notification as read."""

    notification: WatchlistNotificationResponse
