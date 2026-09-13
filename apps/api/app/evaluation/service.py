from datetime import datetime
from uuid import UUID

from app.evaluation.analyzer import SignalEvaluationAnalyzer
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationSummary,
    EvaluationWindow,
    SignalEvaluation,
)


class SignalEvaluationService:
    """Application service for signal evaluation."""

    def __init__(self) -> None:
        self._analyzer = SignalEvaluationAnalyzer()

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
        """Evaluate one historical signal."""

        return self._analyzer.evaluate(
            signal_id=signal_id,
            event_id=event_id,
            instrument_id=instrument_id,
            window=window,
            signal_direction=signal_direction,
            observed_direction=observed_direction,
            signal_confidence=signal_confidence,
            forward_return_pct=forward_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            evaluated_at=evaluated_at,
        )

    def summarize(
        self,
        evaluations: tuple[SignalEvaluation, ...],
    ) -> EvaluationSummary:
        """Summarize historical signal evaluations."""

        return self._analyzer.summarize(evaluations)
