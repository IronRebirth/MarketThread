from datetime import datetime
from uuid import UUID

from app.evaluation.analyzer import SignalEvaluationAnalyzer
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

from .horizon import BacktestHorizon
from .models import (
    BacktestStatus,
    TemporalValidationError,
    TimeAwareBacktestSummary,
    TimeAwareEvaluation,
    TimeAwareObservation,
    WalkForwardFold,
    WalkForwardResult,
)


class TimeAwareBacktestAnalyzer:
    def evaluate(
        self,
        *,
        signal_id: UUID,
        event_id: UUID,
        signal_created_at: datetime,
        observation: TimeAwareObservation | None,
        instrument_id: UUID | None = None,
        signal_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE,
        signal_strength: EvaluationSignalStrength = EvaluationSignalStrength.STRONG,
        recommendation_state: EvaluationRecommendationState = (
            EvaluationRecommendationState.CONSIDER
        ),
        signal_confidence: float = 0.0,
        horizon: BacktestHorizon | None = None,
    ) -> TimeAwareEvaluation:
        resolved_instrument_id = instrument_id

        if resolved_instrument_id is None and observation is not None:
            resolved_instrument_id = observation.instrument_id

        common = {
            "signal_id": signal_id,
            "event_id": event_id,
            "instrument_id": resolved_instrument_id,
            "signal_created_at": signal_created_at,
            "observation": observation,
            "signal_direction": signal_direction,
            "signal_strength": signal_strength,
            "recommendation_state": recommendation_state,
            "signal_confidence": signal_confidence,
            "horizon": horizon,
        }

        if observation is None:
            return TimeAwareEvaluation(
                **common,
                status=BacktestStatus.REJECTED,
                temporal_error=(TemporalValidationError.MISSING_OBSERVATION_TIMESTAMP),
                notes=(
                    "Evaluation rejected because no observation was available.",
                    "Look-ahead observations are excluded from signal evaluation.",
                ),
            )

        if observation.observed_at is None:
            return TimeAwareEvaluation(
                **common,
                status=BacktestStatus.REJECTED,
                temporal_error=(TemporalValidationError.MISSING_OBSERVATION_TIMESTAMP),
                notes=(
                    "Evaluation rejected because the observation timestamp is missing.",
                    "Look-ahead observations are excluded from signal evaluation.",
                ),
            )

        if observation.observed_at < signal_created_at:
            return TimeAwareEvaluation(
                **common,
                status=BacktestStatus.REJECTED,
                temporal_error=TemporalValidationError.OBSERVATION_BEFORE_SIGNAL,
                notes=(
                    "Evaluation rejected because the observation occurs "
                    "before the signal timestamp.",
                    "Look-ahead observations are excluded from signal evaluation.",
                ),
            )

        if observation.observed_at == signal_created_at:
            return TimeAwareEvaluation(
                **common,
                status=BacktestStatus.REJECTED,
                temporal_error=TemporalValidationError.OBSERVATION_AT_SIGNAL,
                notes=(
                    "Evaluation rejected because the observation occurs "
                    "at the signal timestamp.",
                    "Look-ahead observations are excluded from signal evaluation.",
                ),
            )

        if (
            horizon is not None
            and observation.horizon is not None
            and observation.horizon != horizon
        ):
            return TimeAwareEvaluation(
                **common,
                status=BacktestStatus.REJECTED,
                notes=(
                    "Evaluation rejected because the observation horizon "
                    "does not match the requested horizon.",
                ),
            )

        observed_direction = self._classify_return(
            observation.forward_return_pct,
        )

        direction_correct = None

        if (
            signal_direction != EvaluationDirection.UNAVAILABLE
            and observed_direction != EvaluationDirection.UNAVAILABLE
        ):
            direction_correct = signal_direction == observed_direction

        relative_return_pct = None

        if (
            observation.forward_return_pct is not None
            and observation.benchmark_return_pct is not None
        ):
            relative_return_pct = (
                observation.forward_return_pct - observation.benchmark_return_pct
            )

        return TimeAwareEvaluation(
            **common,
            status=BacktestStatus.VALID,
            observed_direction=observed_direction,
            forward_return_pct=observation.forward_return_pct,
            benchmark_return_pct=observation.benchmark_return_pct,
            relative_return_pct=relative_return_pct,
            direction_correct=direction_correct,
            notes=(
                "Observation occurs strictly after the signal timestamp.",
                "Look-ahead observations are excluded from signal evaluation.",
            )
            + (
                ("Evaluation uses the explicitly requested horizon.",)
                if horizon is not None
                else ()
            ),
        )

    def summarize(
        self,
        evaluations: tuple[TimeAwareEvaluation, ...] | list[TimeAwareEvaluation],
    ) -> TimeAwareBacktestSummary:
        evaluations = tuple(evaluations)

        valid = tuple(
            evaluation
            for evaluation in evaluations
            if evaluation.status == BacktestStatus.VALID
        )

        rejected = tuple(
            evaluation
            for evaluation in evaluations
            if evaluation.status == BacktestStatus.REJECTED
        )

        if not evaluations:
            return TimeAwareBacktestSummary(
                total_evaluations=0,
                valid_evaluations=0,
                rejected_evaluations=0,
                observation_count=0,
                notes=("No historical evaluations are available.",),
            )

        summary = SignalEvaluationAnalyzer().summarize(valid)

        return TimeAwareBacktestSummary(
            total_evaluations=len(evaluations),
            valid_evaluations=len(valid),
            rejected_evaluations=len(rejected),
            observation_count=sum(
                evaluation.observation is not None for evaluation in valid
            ),
            directional_accuracy=summary.directional_accuracy,
            average_forward_return_pct=summary.average_forward_return_pct,
            average_relative_return_pct=summary.average_relative_return_pct,
            positive_outcome_rate=summary.positive_outcome_rate,
            notes=(
                "Only temporally valid evaluations are included in "
                "performance metrics.",
                "Look-ahead observations are excluded from signal evaluation.",
            ),
        )

    @staticmethod
    def _classify_return(
        forward_return_pct: float | None,
    ) -> EvaluationDirection:
        if forward_return_pct is None:
            return EvaluationDirection.UNAVAILABLE

        if forward_return_pct > 0:
            return EvaluationDirection.POSITIVE

        if forward_return_pct < 0:
            return EvaluationDirection.NEGATIVE

        return EvaluationDirection.NEUTRAL


class WalkForwardBacktestAnalyzer:
    def create_folds(
        self,
        training_periods: tuple,
        evaluation_periods: tuple,
    ) -> tuple[WalkForwardFold, ...]:
        if len(training_periods) != len(evaluation_periods):
            raise ValueError(
                "Training and evaluation periods must have the same length.",
            )

        return tuple(
            WalkForwardFold(
                fold_number=index,
                training_periods=(training_period,),
                evaluation_periods=(evaluation_period,),
            )
            for index, (training_period, evaluation_period) in enumerate(
                zip(training_periods, evaluation_periods, strict=False),
                start=1,
            )
        )

    def validate(
        self,
        folds: tuple[WalkForwardFold, ...] | list[WalkForwardFold],
        *,
        backtest_id: UUID | None = None,
    ) -> WalkForwardResult:
        folds = tuple(folds)

        if not folds:
            return WalkForwardResult(
                backtest_id=backtest_id,
                folds=(),
                valid=True,
                invalid_fold_numbers=(),
                notes=("No walk-forward folds were supplied.",),
            )

        invalid_fold_numbers = tuple(
            fold.fold_number for fold in folds if not fold.is_temporally_valid()
        )

        if invalid_fold_numbers:
            return WalkForwardResult(
                backtest_id=backtest_id,
                folds=folds,
                valid=False,
                invalid_fold_numbers=invalid_fold_numbers,
                notes=("One or more folds failed temporal validation.",),
            )

        chronology_is_valid = True

        for index in range(1, len(folds)):
            previous = folds[index - 1]
            current = folds[index]

            if current.evaluation_period.start_at < previous.evaluation_period.start_at:
                chronology_is_valid = False
                break

        if not chronology_is_valid:
            return WalkForwardResult(
                backtest_id=backtest_id,
                folds=folds,
                valid=False,
                invalid_fold_numbers=(),
                notes=("Walk-forward folds are not monotonically ordered.",),
            )

        return WalkForwardResult(
            backtest_id=backtest_id,
            folds=folds,
            valid=True,
            invalid_fold_numbers=(),
            notes=("Walk-forward folds passed temporal validation.",),
        )
