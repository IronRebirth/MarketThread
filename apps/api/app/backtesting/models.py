from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BacktestStatus(StrEnum):
    """Status of a time-aware backtest evaluation."""

    VALID = "valid"
    REJECTED = "rejected"


class TemporalValidationError(StrEnum):
    """Reason a historical observation violates temporal ordering."""

    OBSERVATION_BEFORE_SIGNAL = "observation_before_signal"
    OBSERVATION_AT_SIGNAL = "observation_at_signal"
    MISSING_OBSERVATION_TIMESTAMP = "missing_observation_timestamp"


class TimeAwareObservation(BaseModel):
    """Historical market observation used after a signal timestamp."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    observed_at: datetime
    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None


class TimeAwareEvaluation(BaseModel):
    """Temporally valid evaluation of a historical signal."""

    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    signal_created_at: datetime
    observation: TimeAwareObservation
    status: BacktestStatus
    temporal_error: TemporalValidationError | None = None
    relative_return_pct: float | None = None
    notes: tuple[str, ...] = ()


class TimeAwareBacktestSummary(BaseModel):
    """Aggregate summary of temporally valid evaluations."""

    model_config = ConfigDict(frozen=True)

    total_evaluations: int = Field(ge=0)
    valid_evaluations: int = Field(ge=0)
    rejected_evaluations: int = Field(ge=0)
    average_relative_return_pct: float | None = None
    notes: tuple[str, ...] = ()
