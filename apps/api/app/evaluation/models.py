from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationDirection(StrEnum):
    """Observed directional outcome used to evaluate a signal."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNAVAILABLE = "unavailable"


class EvaluationWindow(StrEnum):
    """Forward-looking observation window used for evaluation."""

    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    TWENTY_DAYS = "20d"


class EvaluationSignalStrength(StrEnum):
    """Signal evidence strength recorded at evaluation time."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class EvaluationRecommendationState(StrEnum):
    """Recommendation state recorded at signal creation time."""

    CONSIDER = "consider"
    WATCH = "watch"
    HOLD = "hold"
    REDUCE = "reduce"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class SignalEvaluation(BaseModel):
    """Evaluation of one historical signal against an observed outcome."""

    model_config = ConfigDict(frozen=True)

    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    window: EvaluationWindow
    signal_direction: EvaluationDirection
    observed_direction: EvaluationDirection
    signal_strength: EvaluationSignalStrength
    recommendation_state: EvaluationRecommendationState
    signal_confidence: float = Field(ge=0.0, le=1.0)
    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None
    direction_correct: bool | None = None
    evaluated_at: datetime
    notes: tuple[str, ...] = ()


class EvaluationSummary(BaseModel):
    """Aggregate evaluation metrics for a collection of signal outcomes."""

    model_config = ConfigDict(frozen=True)

    evaluation_count: int = Field(ge=0)
    directional_accuracy: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    notes: tuple[str, ...] = ()


class EvaluationHorizonSummary(BaseModel):
    """Evaluation metrics for one specific forward-looking horizon."""

    model_config = ConfigDict(frozen=True)

    window: EvaluationWindow
    evaluation_count: int = Field(ge=0)
    directional_accuracy: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class EvaluationByHorizonSummary(BaseModel):
    """Aggregate evaluation metrics grouped by forward horizon."""

    model_config = ConfigDict(frozen=True)

    summaries: tuple[EvaluationHorizonSummary, ...] = ()
    notes: tuple[str, ...] = ()


class EvaluationStateSummary(BaseModel):
    """Evaluation metrics for one signal or recommendation state."""

    model_config = ConfigDict(frozen=True)

    state: str = Field(min_length=1, max_length=64)
    evaluation_count: int = Field(ge=0)
    directional_accuracy: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class EvaluationByStateSummary(BaseModel):
    """Aggregate evaluation metrics grouped by signal state."""

    model_config = ConfigDict(frozen=True)

    summaries: tuple[EvaluationStateSummary, ...] = ()
    notes: tuple[str, ...] = ()
