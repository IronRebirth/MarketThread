from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SignalDirection(StrEnum):
    """Directional interpretation of a market signal."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class SignalStrength(StrEnum):
    """Strength of the available evidence supporting a signal."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class SignalOpportunity(StrEnum):
    """Opportunity classification derived from evidence and impact."""

    OPPORTUNITY = "opportunity"
    WATCH = "watch"
    HOLD = "hold"
    REDUCE = "reduce"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class MarketSignal(BaseModel):
    """Structured market signal derived from market intelligence."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    direction: SignalDirection
    strength: SignalStrength
    opportunity: SignalOpportunity
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    time_horizon: str = Field(min_length=1, max_length=32)
    supporting_factors: tuple[str, ...] = ()
    contradicting_factors: tuple[str, ...] = ()
    evidence_article_ids: tuple[UUID, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)
