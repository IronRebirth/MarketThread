from datetime import datetime
from uuid import UUID

from app.backtesting.analyzer import TimeAwareBacktestAnalyzer
from app.backtesting.models import (
    BacktestPeriod,
    TimeAwareBacktestSummary,
    TimeAwareEvaluation,
    TimeAwareObservation,
    WalkForwardFold,
    WalkForwardResult,
)
from app.backtesting.walk_forward import WalkForwardBacktestAnalyzer


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


class WalkForwardBacktestService:
    """Application service for walk-forward backtesting."""

    def __init__(self) -> None:
        self._analyzer = WalkForwardBacktestAnalyzer()

    def create_folds(
        self,
        training_periods: tuple[BacktestPeriod, ...],
        evaluation_periods: tuple[BacktestPeriod, ...],
    ) -> tuple[WalkForwardFold, ...]:
        """Create chronological walk-forward folds."""

        return self._analyzer.create_folds(
            training_periods=training_periods,
            evaluation_periods=evaluation_periods,
        )

    def validate(
        self,
        folds: tuple[WalkForwardFold, ...],
        backtest_id: UUID | None = None,
    ) -> WalkForwardResult:
        """Validate walk-forward folds."""

        return self._analyzer.validate(
            folds=folds,
            backtest_id=backtest_id,
        )
