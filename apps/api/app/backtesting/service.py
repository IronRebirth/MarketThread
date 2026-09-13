from datetime import datetime
from uuid import UUID

from .analyzer import TimeAwareBacktestAnalyzer, WalkForwardBacktestAnalyzer
from .engine import (
    BacktestExecutionEngine,
    BacktestExecutionResult,
    BacktestSignal,
)
from .models import (
    BacktestPeriod,
    TimeAwareBacktestSummary,
    TimeAwareEvaluation,
    TimeAwareObservation,
    WalkForwardFold,
    WalkForwardResult,
)


class TimeAwareBacktestService:
    def __init__(
        self,
        analyzer: TimeAwareBacktestAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer or TimeAwareBacktestAnalyzer()

    def evaluate(
        self,
        signal_id: UUID,
        event_id: UUID,
        signal_created_at: datetime,
        observation: TimeAwareObservation,
        signal_direction=None,
        signal_strength=None,
        recommendation_state=None,
        signal_confidence: float = 0.0,
    ) -> TimeAwareEvaluation:
        kwargs = {
            "signal_id": signal_id,
            "event_id": event_id,
            "signal_created_at": signal_created_at,
            "observation": observation,
            "instrument_id": observation.instrument_id,
            "signal_confidence": signal_confidence,
        }

        if signal_direction is not None:
            kwargs["signal_direction"] = signal_direction

        if signal_strength is not None:
            kwargs["signal_strength"] = signal_strength

        if recommendation_state is not None:
            kwargs["recommendation_state"] = recommendation_state

        return self._analyzer.evaluate(**kwargs)

    def summarize(
        self,
        evaluations: tuple[TimeAwareEvaluation, ...] | list[TimeAwareEvaluation],
    ) -> TimeAwareBacktestSummary:
        return self._analyzer.summarize(evaluations)


class WalkForwardBacktestService:
    def __init__(
        self,
        analyzer: WalkForwardBacktestAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer or WalkForwardBacktestAnalyzer()

    def create_folds(
        self,
        training_periods: tuple[BacktestPeriod, ...] | list[BacktestPeriod],
        evaluation_periods: tuple[BacktestPeriod, ...] | list[BacktestPeriod],
    ) -> tuple[WalkForwardFold, ...]:
        return self._analyzer.create_folds(
            tuple(training_periods),
            tuple(evaluation_periods),
        )

    def validate(
        self,
        folds: tuple[WalkForwardFold, ...] | list[WalkForwardFold],
        *,
        backtest_id: UUID | None = None,
    ) -> WalkForwardResult:
        return self._analyzer.validate(
            tuple(folds),
            backtest_id=backtest_id,
        )


class BacktestExecutionService:
    def __init__(
        self,
        engine: BacktestExecutionEngine | None = None,
    ) -> None:
        self._engine = engine or BacktestExecutionEngine()

    def execute(
        self,
        *,
        folds: tuple[WalkForwardFold, ...] | list[WalkForwardFold],
        signals: tuple[BacktestSignal, ...] | list[BacktestSignal],
        observations: tuple[TimeAwareObservation, ...] | list[TimeAwareObservation],
        backtest_id: UUID | None = None,
    ) -> BacktestExecutionResult:
        return self._engine.execute(
            folds=tuple(folds),
            signals=tuple(signals),
            observations=tuple(observations),
            backtest_id=backtest_id,
        )
