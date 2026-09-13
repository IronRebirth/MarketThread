from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.evaluation.models import EvaluationDirection

from .horizon import BacktestHorizon


class HorizonObservation(BaseModel):
    instrument_id: UUID
    horizon: BacktestHorizon
    observed_at: datetime | None = None
    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None


class HorizonEvaluation(BaseModel):
    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    signal_created_at: datetime

    horizon: BacktestHorizon
    observation: HorizonObservation | None = None

    signal_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE
    observed_direction: EvaluationDirection = EvaluationDirection.UNAVAILABLE

    forward_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None
    direction_correct: bool | None = None

    valid: bool
    notes: tuple[str, ...] = ()


class HorizonBacktestAnalyzer:
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
        if observation is None:
            return HorizonEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=instrument_id,
                signal_created_at=signal_created_at,
                horizon=horizon,
                observation=None,
                signal_direction=signal_direction,
                valid=False,
                notes=("No observation is available for the requested horizon.",),
            )

        if observation.instrument_id != instrument_id:
            return HorizonEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=instrument_id,
                signal_created_at=signal_created_at,
                horizon=horizon,
                observation=observation,
                signal_direction=signal_direction,
                valid=False,
                notes=("Observation instrument does not match the signal instrument.",),
            )

        if observation.horizon != horizon:
            return HorizonEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=instrument_id,
                signal_created_at=signal_created_at,
                horizon=horizon,
                observation=observation,
                signal_direction=signal_direction,
                valid=False,
                notes=("Observation horizon does not match the requested horizon.",),
            )

        if observation.observed_at is None:
            return HorizonEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=instrument_id,
                signal_created_at=signal_created_at,
                horizon=horizon,
                observation=observation,
                signal_direction=signal_direction,
                valid=False,
                notes=("Observation timestamp is required for horizon evaluation.",),
            )

        if observation.observed_at <= signal_created_at:
            return HorizonEvaluation(
                signal_id=signal_id,
                event_id=event_id,
                instrument_id=instrument_id,
                signal_created_at=signal_created_at,
                horizon=horizon,
                observation=observation,
                signal_direction=signal_direction,
                valid=False,
                notes=(
                    "Observation must occur strictly after signal creation.",
                    "Look-ahead observations are excluded from evaluation.",
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

        return HorizonEvaluation(
            signal_id=signal_id,
            event_id=event_id,
            instrument_id=instrument_id,
            signal_created_at=signal_created_at,
            horizon=horizon,
            observation=observation,
            signal_direction=signal_direction,
            observed_direction=observed_direction,
            forward_return_pct=observation.forward_return_pct,
            benchmark_return_pct=observation.benchmark_return_pct,
            relative_return_pct=relative_return_pct,
            direction_correct=direction_correct,
            valid=True,
            notes=(
                "Observation occurs strictly after signal creation.",
                "Evaluation uses the explicitly requested horizon.",
            ),
        )

    def summarize(
        self,
        evaluations: tuple[HorizonEvaluation, ...] | list[HorizonEvaluation],
    ) -> dict[BacktestHorizon, dict[str, float | int | None]]:
        summaries: dict[BacktestHorizon, dict[str, float | int | None]] = {}

        for horizon in BacktestHorizon:
            grouped = [
                evaluation
                for evaluation in evaluations
                if evaluation.horizon == horizon and evaluation.valid
            ]

            forward_returns = [
                evaluation.forward_return_pct
                for evaluation in grouped
                if evaluation.forward_return_pct is not None
            ]

            relative_returns = [
                evaluation.relative_return_pct
                for evaluation in grouped
                if evaluation.relative_return_pct is not None
            ]

            direction_results = [
                evaluation.direction_correct
                for evaluation in grouped
                if evaluation.direction_correct is not None
            ]

            positive_results = [
                evaluation.forward_return_pct
                for evaluation in grouped
                if evaluation.forward_return_pct is not None
            ]

            summaries[horizon] = {
                "evaluation_count": len(grouped),
                "directional_accuracy": (
                    sum(direction_results) / len(direction_results)
                    if direction_results
                    else None
                ),
                "average_forward_return_pct": (
                    sum(forward_returns) / len(forward_returns)
                    if forward_returns
                    else None
                ),
                "average_relative_return_pct": (
                    sum(relative_returns) / len(relative_returns)
                    if relative_returns
                    else None
                ),
                "positive_outcome_rate": (
                    sum(value > 0 for value in positive_results) / len(positive_results)
                    if positive_results
                    else None
                ),
            }

        return summaries

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
