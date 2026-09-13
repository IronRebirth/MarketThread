from datetime import datetime
from uuid import UUID

from app.evaluation.models import EvaluationDirection

from .horizon import BacktestHorizon
from .horizon_analyzer import (
    HorizonBacktestAnalyzer,
    HorizonEvaluation,
    HorizonObservation,
)


class HorizonBacktestService:
    def __init__(
        self,
        analyzer: HorizonBacktestAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer or HorizonBacktestAnalyzer()

    def evaluate(
        self,
        *,
        signal_id: UUID,
        event_id: UUID,
        instrument_id: UUID,
        signal_created_at: datetime,
        horizon: BacktestHorizon,
        observation: HorizonObservation | None,
        signal_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE,
    ) -> HorizonEvaluation:
        return self._analyzer.evaluate(
            signal_id=signal_id,
            event_id=event_id,
            instrument_id=instrument_id,
            signal_created_at=signal_created_at,
            horizon=horizon,
            observation=observation,
            signal_direction=signal_direction,
        )

    def summarize(
        self,
        evaluations: tuple[HorizonEvaluation, ...] | list[HorizonEvaluation],
    ) -> dict:
        return self._analyzer.summarize(evaluations)
