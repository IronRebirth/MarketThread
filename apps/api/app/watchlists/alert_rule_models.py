from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlertRuleType(StrEnum):
    """Supported watchlist alert rule types."""

    EVENT_IMPACT = "event_impact"


class WatchlistAlertRuleConditions(BaseModel):
    """Deterministic filters for persisted event-impact alerts."""

    model_config = ConfigDict(frozen=True)

    event_types: tuple[str, ...] = Field(default=())
    directions: tuple[str, ...] = Field(default=())
    minimum_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    minimum_event_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class WatchlistAlertRule(BaseModel):
    """Persisted notification eligibility rule for a watchlist."""

    model_config = ConfigDict(frozen=True)

    rule_id: UUID
    watchlist_id: UUID
    name: str = Field(min_length=1, max_length=100)
    rule_type: AlertRuleType
    conditions: WatchlistAlertRuleConditions
    enabled: bool
    created_at: datetime
    updated_at: datetime
