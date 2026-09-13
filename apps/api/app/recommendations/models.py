from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecommendationState(StrEnum):
    """Research-oriented recommendation state."""

    CONSIDER = "consider"
    WATCH = "watch"
    HOLD = "hold"
    REDUCE = "reduce"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Recommendation(BaseModel):
    """Explainable research recommendation derived from structured intelligence."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    state: RecommendationState
    signal_direction: str = Field(min_length=1, max_length=32)
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence_level: str = Field(min_length=1, max_length=32)
    risk_level: str = Field(min_length=1, max_length=32)
    time_horizon: str = Field(min_length=1, max_length=32)
    supporting_factors: tuple[str, ...] = ()
    contradicting_factors: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    evidence_article_ids: tuple[UUID, ...] = ()
    rationale: str = Field(min_length=1)
