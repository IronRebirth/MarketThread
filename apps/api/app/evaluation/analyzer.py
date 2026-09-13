from datetime import datetime
from uuid import UUID

from app.evaluation.models import (
    EvaluationByHorizonSummary,
    EvaluationDirection,
    EvaluationHorizonSummary,
    EvaluationSummary,
    EvaluationWindow,
    SignalEvaluation,
)


class SignalEvaluationAnalyzer:
    """Evaluate historical signals against observed forward outcomes."""

    def evaluate(
        self,
        signal_id: UUID,
        event_id: UUID,
        instrument_id: UUID,
        window: EvaluationWindow,
        signal_direction: EvaluationDirection,
        observed_direction: EvaluationDirection,
        signal_confidence: float,
        forward_return_pct: float | None,
        benchmark_return_pct: float | None,
        evaluated_at: datetime,
    ) -> SignalEvaluation:
        """Evaluate one signal without claiming causal attribution."""

        relative_return_pct = None

        if forward_return_pct is not None and benchmark_return_pct is not None:
            relative_return_pct = forward_return_pct - benchmark_return_pct

        direction_correct = self._direction_correct(
            signal_direction,
            observed_direction,
        )

        notes = self._build_notes(
            signal_direction=signal_direction,
            observed_direction=observed_direction,
            direction_correct=direction_correct,
        )

        return SignalEvaluation(
            signal_id=signal_id,
            event_id=event_id,
            instrument_id=instrument_id,
            window=window,
            signal_direction=signal_direction,
            observed_direction=observed_direction,
            signal_confidence=signal_confidence,
            forward_return_pct=forward_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            relative_return_pct=relative_return_pct,
            direction_correct=direction_correct,
            evaluated_at=evaluated_at,
            notes=notes,
        )

    def summarize(
        self,
        evaluations: tuple[SignalEvaluation, ...],
    ) -> EvaluationSummary:
        """Aggregate historical signal evaluation results."""

        evaluated_directions = [
            evaluation.direction_correct
            for evaluation in evaluations
            if evaluation.direction_correct is not None
        ]

        returns = [
            evaluation.forward_return_pct
            for evaluation in evaluations
            if evaluation.forward_return_pct is not None
        ]

        relative_returns = [
            evaluation.relative_return_pct
            for evaluation in evaluations
            if evaluation.relative_return_pct is not None
        ]

        positive_outcomes = [
            evaluation
            for evaluation in evaluations
            if evaluation.observed_direction == EvaluationDirection.POSITIVE
        ]

        directional_accuracy = None

        if evaluated_directions:
            directional_accuracy = sum(evaluated_directions) / len(
                evaluated_directions,
            )

        average_forward_return_pct = self._average(returns)
        average_relative_return_pct = self._average(relative_returns)

        positive_outcome_rate = None

        if evaluations:
            positive_outcome_rate = len(positive_outcomes) / len(evaluations)

        notes = self._build_summary_notes(
            evaluations=evaluations,
            directional_accuracy=directional_accuracy,
        )

        return EvaluationSummary(
            evaluation_count=len(evaluations),
            directional_accuracy=directional_accuracy,
            average_forward_return_pct=average_forward_return_pct,
            average_relative_return_pct=average_relative_return_pct,
            positive_outcome_rate=positive_outcome_rate,
            notes=notes,
        )

    def summarize_by_horizon(
        self,
        evaluations: tuple[SignalEvaluation, ...],
    ) -> EvaluationByHorizonSummary:
        """Aggregate historical evaluation results separately by horizon."""

        summaries = tuple(
            self._summarize_horizon(evaluations, window) for window in EvaluationWindow
        )

        return EvaluationByHorizonSummary(
            summaries=summaries,
            notes=self._build_horizon_summary_notes(
                evaluations=evaluations,
            ),
        )

    @staticmethod
    def _summarize_horizon(
        evaluations: tuple[SignalEvaluation, ...],
        window: EvaluationWindow,
    ) -> EvaluationHorizonSummary:
        """Summarize evaluations for one horizon."""

        window_evaluations = tuple(
            evaluation for evaluation in evaluations if evaluation.window == window
        )

        evaluated_directions = [
            evaluation.direction_correct
            for evaluation in window_evaluations
            if evaluation.direction_correct is not None
        ]

        returns = [
            evaluation.forward_return_pct
            for evaluation in window_evaluations
            if evaluation.forward_return_pct is not None
        ]

        relative_returns = [
            evaluation.relative_return_pct
            for evaluation in window_evaluations
            if evaluation.relative_return_pct is not None
        ]

        positive_outcomes = sum(
            evaluation.observed_direction == EvaluationDirection.POSITIVE
            for evaluation in window_evaluations
        )

        directional_accuracy = None

        if evaluated_directions:
            directional_accuracy = sum(evaluated_directions) / len(
                evaluated_directions,
            )

        positive_outcome_rate = None

        if window_evaluations:
            positive_outcome_rate = positive_outcomes / len(
                window_evaluations,
            )

        return EvaluationHorizonSummary(
            window=window,
            evaluation_count=len(window_evaluations),
            directional_accuracy=directional_accuracy,
            average_forward_return_pct=SignalEvaluationAnalyzer._average(
                returns,
            ),
            average_relative_return_pct=SignalEvaluationAnalyzer._average(
                relative_returns,
            ),
            positive_outcome_rate=positive_outcome_rate,
        )

    @staticmethod
    def _direction_correct(
        signal_direction: EvaluationDirection,
        observed_direction: EvaluationDirection,
    ) -> bool | None:
        """Determine whether a directional signal matched the observation."""

        if (
            signal_direction == EvaluationDirection.UNAVAILABLE
            or observed_direction == EvaluationDirection.UNAVAILABLE
            or signal_direction == EvaluationDirection.NEUTRAL
            or observed_direction == EvaluationDirection.NEUTRAL
        ):
            return None

        return signal_direction == observed_direction

    @staticmethod
    def _average(values: list[float]) -> float | None:
        """Calculate the arithmetic mean for available values."""

        if not values:
            return None

        return sum(values) / len(values)

    @staticmethod
    def _build_notes(
        signal_direction: EvaluationDirection,
        observed_direction: EvaluationDirection,
        direction_correct: bool | None,
    ) -> tuple[str, ...]:
        """Create notes describing the individual evaluation."""

        if direction_correct is True:
            return (
                "Signal direction matched the observed market direction.",
                "Observed movement is an outcome measurement, not proof of causation.",
            )

        if direction_correct is False:
            return (
                "Signal direction did not match the observed market direction.",
                "Observed movement is an outcome measurement, not proof of causation.",
            )

        return (
            (
                "Directional accuracy is unavailable for neutral or "
                "unavailable observations."
            ),
            "Observed movement is an outcome measurement, not proof of causation.",
        )

    @staticmethod
    def _build_summary_notes(
        evaluations: tuple[SignalEvaluation, ...],
        directional_accuracy: float | None,
    ) -> tuple[str, ...]:
        """Create aggregate evaluation notes."""

        if not evaluations:
            return ("No historical signal evaluations are available.",)

        notes = [
            (f"{len(evaluations)} historical signal evaluations were processed."),
        ]

        if directional_accuracy is not None:
            notes.append(
                (
                    f"Directional accuracy across evaluable signals was "
                    f"{directional_accuracy:.2%}."
                ),
            )
        else:
            notes.append(
                "Directional accuracy was unavailable for this evaluation set.",
            )

        notes.append(
            "Historical association does not establish that a signal caused "
            "the observed market outcome.",
        )

        return tuple(notes)

    @staticmethod
    def _build_horizon_summary_notes(
        evaluations: tuple[SignalEvaluation, ...],
    ) -> tuple[str, ...]:
        """Create notes for horizon-level evaluation results."""

        if not evaluations:
            return ("No historical signal evaluations are available by horizon.",)

        return (
            (
                f"{len(evaluations)} historical evaluations were grouped "
                "by forward observation horizon."
            ),
            (
                "Horizon comparisons describe observed outcomes and do not "
                "establish causation."
            ),
        )
