from datetime import datetime
from uuid import UUID

from app.backtesting.models import (
    BacktestStatus,
    TemporalValidationError,
    TimeAwareBacktestSummary,
    TimeAwareEvaluation,
    TimeAwareObservation,
)


class TimeAwareBacktestAnalyzer:
    """Validate and evaluate historical observations without look-ahead bias."""

    def evaluate(
        self,
        signal_id: UUID,
        event_id: UUID,
        signal_created_at: datetime,
        observation: TimeAwareObservation,
    ) -> TimeAwareEvaluation:
        """Evaluate an observation only when it occurs after the signal."""

        temporal_error = self._validate_observation_time(
            signal_created_at=signal_created_at,
            observed_at=observation.observed_at,
        )

        if temporal_error is not None:
            return TimeAwareEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=observation.instrument_id,
                signal_created_at=signal_created_at,
                observation=observation,
                status=BacktestStatus.REJECTED,
                temporal_error=temporal_error,
                notes=(
                    "Observation was rejected because it violates "
                    "the signal-to-observation temporal ordering.",
                    "Look-ahead observations cannot be used in this evaluation.",
                ),
            )

        relative_return_pct = None

        if (
            observation.forward_return_pct is not None
            and observation.benchmark_return_pct is not None
        ):
            relative_return_pct = (
                observation.forward_return_pct - observation.benchmark_return_pct
            )

        return TimeAwareEvaluation(
            signal_id=signal_id,
            event_id=event_id,
            instrument_id=observation.instrument_id,
            signal_created_at=signal_created_at,
            observation=observation,
            status=BacktestStatus.VALID,
            relative_return_pct=relative_return_pct,
            notes=(
                "Observation occurs strictly after the signal timestamp.",
                "Look-ahead observations are excluded from signal evaluation.",
            ),
        )

    def summarize(
        self,
        evaluations: tuple[TimeAwareEvaluation, ...],
    ) -> TimeAwareBacktestSummary:
        """Summarize valid and rejected temporal evaluations."""

        valid_evaluations = [
            evaluation
            for evaluation in evaluations
            if evaluation.status == BacktestStatus.VALID
        ]

        rejected_evaluations = [
            evaluation
            for evaluation in evaluations
            if evaluation.status == BacktestStatus.REJECTED
        ]

        relative_returns = [
            evaluation.relative_return_pct
            for evaluation in valid_evaluations
            if evaluation.relative_return_pct is not None
        ]

        average_relative_return_pct = self._average(relative_returns)

        notes = self._build_summary_notes(
            evaluations=evaluations,
            valid_count=len(valid_evaluations),
            rejected_count=len(rejected_evaluations),
        )

        return TimeAwareBacktestSummary(
            total_evaluations=len(evaluations),
            valid_evaluations=len(valid_evaluations),
            rejected_evaluations=len(rejected_evaluations),
            average_relative_return_pct=average_relative_return_pct,
            notes=notes,
        )

    @staticmethod
    def _validate_observation_time(
        signal_created_at: datetime,
        observed_at: datetime,
    ) -> TemporalValidationError | None:
        """Reject observations that are not strictly after the signal."""

        if observed_at < signal_created_at:
            return TemporalValidationError.OBSERVATION_BEFORE_SIGNAL

        if observed_at == signal_created_at:
            return TemporalValidationError.OBSERVATION_AT_SIGNAL

        return None

    @staticmethod
    def _average(values: list[float]) -> float | None:
        """Calculate the arithmetic mean for available returns."""

        if not values:
            return None

        return sum(values) / len(values)

    @staticmethod
    def _build_summary_notes(
        evaluations: tuple[TimeAwareEvaluation, ...],
        valid_count: int,
        rejected_count: int,
    ) -> tuple[str, ...]:
        """Build notes describing temporal evaluation quality."""

        if not evaluations:
            return ("No historical evaluations were supplied.",)

        notes = [
            (
                f"{valid_count} of {len(evaluations)} evaluations "
                "passed temporal validation."
            ),
        ]

        if rejected_count:
            notes.append(
                (
                    f"{rejected_count} evaluations were rejected because "
                    "their observations were not strictly after the signal."
                ),
            )

        notes.append(
            "Look-ahead observations are excluded from time-aware evaluation.",
        )

        return tuple(notes)
