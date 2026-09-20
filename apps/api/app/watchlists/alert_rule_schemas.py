from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.watchlists.alert_rule_models import (
    AlertRuleType,
    WatchlistAlertRuleConditions,
)


class WatchlistAlertRuleConditionsRequest(BaseModel):
    """API input for deterministic event-impact alert filters."""

    model_config = ConfigDict(extra="forbid")

    event_types: tuple[str, ...] = Field(default=())
    directions: tuple[str, ...] = Field(default=())
    minimum_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    minimum_event_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    @field_validator("event_types", "directions")
    @classmethod
    def normalize_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize rule filter values and reject blank entries."""

        normalized = []

        for value in values:
            cleaned = value.strip().lower()

            if not cleaned:
                raise ValueError("Rule filter values must not be blank.")

            normalized.append(cleaned)

        return tuple(sorted(set(normalized)))


class WatchlistAlertRuleCreateRequest(BaseModel):
    """API input for creating a watchlist alert rule."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    rule_type: AlertRuleType = AlertRuleType.EVENT_IMPACT
    conditions: WatchlistAlertRuleConditionsRequest = Field(
        default_factory=WatchlistAlertRuleConditionsRequest,
    )
    enabled: bool = True


class WatchlistAlertRuleUpdateRequest(BaseModel):
    """API input for partially updating a watchlist alert rule."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    conditions: WatchlistAlertRuleConditionsRequest | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "WatchlistAlertRuleUpdateRequest":
        """Reject empty PATCH requests."""

        if self.name is None and self.conditions is None and self.enabled is None:
            raise ValueError("At least one alert rule field must be provided.")

        return self


class WatchlistAlertRuleResponse(BaseModel):
    """API representation of a watchlist alert rule."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    watchlist_id: str
    name: str
    rule_type: AlertRuleType
    conditions: WatchlistAlertRuleConditions
    enabled: bool
    created_at: str
    updated_at: str
