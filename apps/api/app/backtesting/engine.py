from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .analyzer import TimeAwareBacktestAnalyzer
from .horizon import BacktestHorizon
from .market_data_quality import BacktestMarketDataHorizonQuality
from .models import (
    BacktestExecutionResult,
    BacktestFoldResult,
    BacktestStatus,
    TimeAwareEvaluation,
    TimeAwareObservation,
    WalkForwardFold,
)


class BacktestSignal(BaseModel):
    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    created_at: datetime
    direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE
    signal_strength: EvaluationSignalStrength = EvaluationSignalStrength.STRONG
    recommendation_state: EvaluationRecommendationState = (
        EvaluationRecommendationState.CONSIDER
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    horizons: tuple[BacktestHorizon, ...] = ()


class BacktestExecutionEngine:
    def __init__(
        self,
        analyzer: TimeAwareBacktestAnalyzer | None = None,
    ) -> None:
        self.analyzer = analyzer or TimeAwareBacktestAnalyzer()

    def execute(
        self,
        *,
        folds: tuple[WalkForwardFold, ...] | list[WalkForwardFold],
        signals: tuple[BacktestSignal, ...] | list[BacktestSignal],
        observations: tuple[TimeAwareObservation, ...] | list[TimeAwareObservation],
        backtest_id: UUID | None = None,
        market_data_expected_count: int | None = None,
        market_data_resolved_count: int | None = None,
        market_data_horizon_quality: (
            tuple[BacktestMarketDataHorizonQuality, ...] | None
        ) = None,
    ) -> BacktestExecutionResult:
        resolved_backtest_id = backtest_id or uuid4()
        folds = tuple(folds)
        signals = tuple(signals)
        observations = tuple(observations)

        if market_data_expected_count is not None:
            if market_data_expected_count < 0:
                raise ValueError(
                    "market_data_expected_count must be non-negative.",
                )

        if market_data_resolved_count is not None:
            if market_data_resolved_count < 0:
                raise ValueError(
                    "market_data_resolved_count must be non-negative.",
                )

        if (
            market_data_expected_count is not None
            and market_data_resolved_count is not None
            and market_data_resolved_count > market_data_expected_count
        ):
            raise ValueError(
                "market_data_resolved_count cannot exceed market_data_expected_count.",
            )

        market_data_coverage_ratio = None

        if market_data_expected_count:
            market_data_coverage_ratio = min(
                market_data_resolved_count / market_data_expected_count
                if market_data_resolved_count is not None
                else 0.0,
                1.0,
            )

        invalid_fold_numbers = tuple(
            fold.fold_number for fold in folds if not fold.is_temporally_valid()
        )

        chronology_is_valid = True

        for index in range(1, len(folds)):
            previous = folds[index - 1]
            current = folds[index]

            if current.evaluation_period.start_at < previous.evaluation_period.start_at:
                chronology_is_valid = False
                break

        fold_results: list[BacktestFoldResult] = []

        for fold in folds:
            fold_is_valid = fold.is_temporally_valid()
            fold_evaluations: list[TimeAwareEvaluation] = []

            if not fold_is_valid:
                fold_results.append(
                    BacktestFoldResult(
                        fold_number=fold.fold_number,
                        training_periods=fold.training_periods,
                        evaluation_periods=fold.evaluation_periods,
                        evaluations=(),
                        valid=False,
                    ),
                )
                continue

            evaluation_start = fold.evaluation_period.start_at
            evaluation_end = fold.evaluation_period.end_at

            evaluation_signals = [
                signal
                for signal in signals
                if evaluation_start <= signal.created_at < evaluation_end
            ]

            for signal in evaluation_signals:
                if signal.horizons:
                    self._append_horizon_evaluations(
                        fold_evaluations=fold_evaluations,
                        signal=signal,
                        observations=observations,
                    )
                else:
                    self._append_legacy_evaluation(
                        fold_evaluations=fold_evaluations,
                        signal=signal,
                        observations=observations,
                    )

            fold_results.append(
                BacktestFoldResult(
                    fold_number=fold.fold_number,
                    training_periods=fold.training_periods,
                    evaluation_periods=fold.evaluation_periods,
                    evaluations=tuple(fold_evaluations),
                    valid=True,
                ),
            )

        all_evaluations = tuple(
            evaluation
            for fold_result in fold_results
            for evaluation in fold_result.evaluations
        )

        valid_count = len(
            tuple(
                evaluation
                for evaluation in all_evaluations
                if evaluation.status == BacktestStatus.VALID
            )
        )

        rejected_count = len(
            tuple(
                evaluation
                for evaluation in all_evaluations
                if evaluation.status == BacktestStatus.REJECTED
            )
        )

        valid = bool(folds) and not invalid_fold_numbers and chronology_is_valid

        if not folds:
            valid = False

        notes: tuple[str, ...] = (
            "Only observations strictly after signal creation are eligible.",
            "The earliest eligible observation is selected for each signal "
            "and horizon.",
        )

        if invalid_fold_numbers:
            notes += ("One or more walk-forward folds failed temporal validation.",)

        if not chronology_is_valid:
            notes += ("Walk-forward fold ordering failed temporal validation.",)

        return BacktestExecutionResult(
            backtest_id=resolved_backtest_id,
            fold_results=tuple(fold_results),
            valid=valid,
            evaluation_count=len(all_evaluations),
            valid_evaluation_count=valid_count,
            rejected_evaluation_count=rejected_count,
            market_data_expected_count=market_data_expected_count,
            market_data_resolved_count=market_data_resolved_count,
            market_data_coverage_ratio=market_data_coverage_ratio,
            market_data_horizon_quality=market_data_horizon_quality,
            notes=notes,
        )

    def _append_legacy_evaluation(
        self,
        *,
        fold_evaluations: list[TimeAwareEvaluation],
        signal: BacktestSignal,
        observations: tuple[TimeAwareObservation, ...],
    ) -> None:
        eligible_observations = self._eligible_observations(
            signal=signal,
            observations=observations,
            horizon=None,
        )

        if not eligible_observations:
            return

        evaluation = self.analyzer.evaluate(
            signal_id=signal.signal_id,
            event_id=signal.event_id,
            instrument_id=signal.instrument_id,
            signal_created_at=signal.created_at,
            observation=eligible_observations[0],
            signal_direction=signal.direction,
            signal_strength=signal.signal_strength,
            recommendation_state=signal.recommendation_state,
            signal_confidence=signal.confidence,
        )

        if evaluation.status == BacktestStatus.VALID:
            fold_evaluations.append(evaluation)

    def _append_horizon_evaluations(
        self,
        *,
        fold_evaluations: list[TimeAwareEvaluation],
        signal: BacktestSignal,
        observations: tuple[TimeAwareObservation, ...],
    ) -> None:
        for horizon in signal.horizons:
            eligible_observations = self._eligible_observations(
                signal=signal,
                observations=observations,
                horizon=horizon,
            )

            if not eligible_observations:
                continue

            evaluation = self.analyzer.evaluate(
                signal_id=signal.signal_id,
                event_id=signal.event_id,
                instrument_id=signal.instrument_id,
                signal_created_at=signal.created_at,
                observation=eligible_observations[0],
                signal_direction=signal.direction,
                signal_strength=signal.signal_strength,
                recommendation_state=signal.recommendation_state,
                signal_confidence=signal.confidence,
                horizon=horizon,
            )

            if evaluation.status == BacktestStatus.VALID:
                fold_evaluations.append(evaluation)

    @staticmethod
    def _eligible_observations(
        *,
        signal: BacktestSignal,
        observations: tuple[TimeAwareObservation, ...],
        horizon: BacktestHorizon | None,
    ) -> list[TimeAwareObservation]:
        eligible = [
            observation
            for observation in observations
            if (
                observation.instrument_id == signal.instrument_id
                and observation.observed_at is not None
                and observation.observed_at > signal.created_at
                and (horizon is None or observation.horizon == horizon)
            )
        ]

        eligible.sort(
            key=lambda observation: (
                observation.observed_at or datetime.max.replace(tzinfo=UTC)
            ),
        )

        return eligible


__all__ = [
    "BacktestExecutionEngine",
    "BacktestExecutionResult",
    "BacktestFoldResult",
    "BacktestSignal",
    "TimeAwareObservation",
]
