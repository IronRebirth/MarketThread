from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OutcomeDirection(StrEnum):
    """Observed directional movement after an event."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNAVAILABLE = "unavailable"


class OutcomeWindow(StrEnum):
    """Observation window used to evaluate an event outcome."""

    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    TWENTY_DAYS = "20d"


class HistoricalOutcome(BaseModel):
    """Observed market outcome following a detected market event."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    instrument_id: UUID
    observed_at: datetime
    window: OutcomeWindow
    start_price: float | None = Field(default=None, ge=0)
    end_price: float | None = Field(default=None, ge=0)
    return_pct: float | None = None
    direction: OutcomeDirection
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None
    source: str = Field(min_length=1, max_length=64)


class HistoricalEventAnalysis(BaseModel):
    """Historical analysis of an event and its observed market outcomes."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    analyzed_at: datetime
    outcomes: tuple[HistoricalOutcome, ...] = ()
    observation_count: int = Field(ge=0)
    notes: tuple[str, ...] = ()
