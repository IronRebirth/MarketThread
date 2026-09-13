from datetime import datetime
from uuid import UUID

from app.backtesting.analyzer import TimeAwareBacktestAnalyzer
from app.backtesting.models import (
    TimeAwareBacktestSummary,
    TimeAwareEvaluation,
    TimeAwareObservation,
)


class TimeAwareBacktestService:
    """Application service for time-aware backtesting."""

    def __init__(self) -> None:
        self._analyzer = TimeAwareBacktestAnalyzer()

    def evaluate(
        self,
        signal_id: UUID,
        event_id: UUID,
        signal_created_at: datetime,
        observation: TimeAwareObservation,
    ) -> TimeAwareEvaluation:
        """Evaluate one historical observation with temporal validation."""

        return self._analyzer.evaluate(
            signal_id=signal_id,
            event_id=event_id,
            signal_created_at=signal_created_at,
            observation=observation,
        )

    def summarize(
        self,
        evaluations: tuple[TimeAwareEvaluation, ...],
    ) -> TimeAwareBacktestSummary:
        """Summarize time-aware evaluations."""

        return self._analyzer.summarize(evaluations)
