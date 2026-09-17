from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .horizon import BacktestHorizon
from .market_data_quality import BacktestMarketDataHorizonQuality


class BacktestStatus(StrEnum):
    VALID = "valid"
    REJECTED = "rejected"


class TemporalValidationError(StrEnum):
    OBSERVATION_BEFORE_SIGNAL = "observation_before_signal"
    OBSERVATION_AT_SIGNAL = "observation_at_signal"
    MISSING_OBSERVATION_TIMESTAMP = "missing_observation_timestamp"


class TimeAwareObservation(BaseModel):
    instrument_id: UUID
    observed_at: datetime | None = None
    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    horizon: BacktestHorizon | None = None


class TimeAwareEvaluation(BaseModel):
    signal_id: UUID
    event_id: UUID
    instrument_id: UUID | None = None
    signal_created_at: datetime
    observation: TimeAwareObservation | None = None
    status: BacktestStatus
    temporal_error: TemporalValidationError | None = None

    signal_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE
    observed_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE
    signal_strength: EvaluationSignalStrength = EvaluationSignalStrength.STRONG
    recommendation_state: EvaluationRecommendationState = (
        EvaluationRecommendationState.CONSIDER
    )
    signal_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    horizon: BacktestHorizon | None = None

    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None
    direction_correct: bool | None = None

    notes: tuple[str, ...] = ()


class TimeAwareBacktestSummary(BaseModel):
    total_evaluations: int
    valid_evaluations: int
    rejected_evaluations: int
    observation_count: int
    directional_accuracy: float | None = None
    average_forward_return_pct: float | None = None
    average_relative_return_pct: float | None = None
    positive_outcome_rate: float | None = None
    notes: tuple[str, ...] = ()


class BacktestPeriod(BaseModel):
    start_at: datetime
    end_at: datetime

    @property
    def start(self) -> datetime:
        return self.start_at

    @property
    def end(self) -> datetime:
        return self.end_at

    def is_valid(self) -> bool:
        return self.end_at > self.start_at


class BacktestRunConfiguration(BaseModel):
    """Immutable configuration snapshot persisted with a completed run."""

    model_config = ConfigDict(frozen=True)

    training_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
    )
    evaluation_periods: tuple[BacktestPeriod, ...] = Field(
        min_length=1,
    )
    benchmark_instrument_id: UUID | None = None


class WalkForwardFold(BaseModel):
    fold_number: int
    training_periods: tuple[BacktestPeriod, ...]
    evaluation_periods: tuple[BacktestPeriod, ...]

    @property
    def training_period(self) -> BacktestPeriod:
        return self.training_periods[-1]

    @property
    def evaluation_period(self) -> BacktestPeriod:
        return self.evaluation_periods[0]

    def is_temporally_valid(self) -> bool:
        if not self.training_periods or not self.evaluation_periods:
            return False

        if not all(period.is_valid() for period in self.training_periods):
            return False

        if not all(period.is_valid() for period in self.evaluation_periods):
            return False

        return self.evaluation_period.start_at >= self.training_period.end_at


class WalkForwardResult(BaseModel):
    backtest_id: UUID | None = None
    folds: tuple[WalkForwardFold, ...] = ()
    valid: bool
    invalid_fold_numbers: tuple[int, ...] = ()
    notes: tuple[str, ...] = ()


class BacktestFoldResult(BaseModel):
    fold_number: int
    training_periods: tuple[BacktestPeriod, ...]
    evaluation_periods: tuple[BacktestPeriod, ...]
    evaluations: tuple[TimeAwareEvaluation, ...] = ()
    valid: bool = True

    @property
    def training_period(self) -> BacktestPeriod:
        return self.training_periods[-1]

    @property
    def evaluation_period(self) -> BacktestPeriod:
        return self.evaluation_periods[0]


class BacktestExecutionResult(BaseModel):
    backtest_id: UUID
    fold_results: tuple[BacktestFoldResult, ...] = ()
    valid: bool
    evaluation_count: int
    valid_evaluation_count: int
    rejected_evaluation_count: int

    market_data_expected_count: int | None = None
    market_data_resolved_count: int | None = None
    market_data_coverage_ratio: float | None = None

    market_data_horizon_quality: tuple[BacktestMarketDataHorizonQuality, ...] | None = (
        None
    )

    notes: tuple[str, ...] = ()

    @property
    def folds(self) -> tuple[BacktestFoldResult, ...]:
        return self.fold_results

    @property
    def evaluations(self) -> list[TimeAwareEvaluation]:
        return [
            evaluation
            for fold_result in self.fold_results
            for evaluation in fold_result.evaluations
        ]

    @property
    def horizon_evaluations(self) -> list[TimeAwareEvaluation]:
        return [
            evaluation
            for evaluation in self.evaluations
            if evaluation.horizon is not None
        ]
