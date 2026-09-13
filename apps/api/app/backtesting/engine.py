from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.backtesting.analyzer import TimeAwareBacktestAnalyzer
from app.backtesting.models import (
    BacktestStatus,
    TimeAwareEvaluation,
    TimeAwareObservation,
    WalkForwardFold,
)


@dataclass(frozen=True)
class BacktestSignal:
    """Historical signal available for backtest execution."""

    signal_id: UUID
    event_id: UUID
    instrument_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class BacktestFoldResult:
    """Evaluation results produced for one walk-forward fold."""

    fold_number: int
    evaluations: tuple[TimeAwareEvaluation, ...]
    valid: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BacktestExecutionResult:
    """Complete execution result for a walk-forward backtest."""

    backtest_id: UUID
    fold_results: tuple[BacktestFoldResult, ...]
    valid: bool
    evaluation_count: int
    valid_evaluation_count: int
    rejected_evaluation_count: int
    notes: tuple[str, ...] = ()


class BacktestExecutionEngine:
    """Execute historical signal evaluations across walk-forward folds."""

    def __init__(self) -> None:
        self._analyzer = TimeAwareBacktestAnalyzer()

    def execute(
        self,
        folds: tuple[WalkForwardFold, ...],
        signals: tuple[BacktestSignal, ...],
        observations: tuple[TimeAwareObservation, ...],
        backtest_id: UUID | None = None,
    ) -> BacktestExecutionResult:
        """Execute signals against the first eligible forward observation."""

        execution_id = backtest_id or uuid4()

        fold_results = tuple(
            self._execute_fold(
                fold=fold,
                signals=signals,
                observations=observations,
            )
            for fold in folds
        )

        all_evaluations = tuple(
            evaluation
            for fold_result in fold_results
            for evaluation in fold_result.evaluations
        )

        valid = bool(folds) and all(fold_result.valid for fold_result in fold_results)

        valid_evaluation_count = sum(
            evaluation.status == BacktestStatus.VALID for evaluation in all_evaluations
        )

        rejected_evaluation_count = sum(
            evaluation.status == BacktestStatus.REJECTED
            for evaluation in all_evaluations
        )

        notes = self._build_notes(
            folds=folds,
            fold_results=fold_results,
            evaluation_count=len(all_evaluations),
        )

        return BacktestExecutionResult(
            backtest_id=execution_id,
            fold_results=fold_results,
            valid=valid,
            evaluation_count=len(all_evaluations),
            valid_evaluation_count=valid_evaluation_count,
            rejected_evaluation_count=rejected_evaluation_count,
            notes=notes,
        )

    def _execute_fold(
        self,
        fold: WalkForwardFold,
        signals: tuple[BacktestSignal, ...],
        observations: tuple[TimeAwareObservation, ...],
    ) -> BacktestFoldResult:
        """Execute evaluations for one walk-forward fold."""

        if not fold.is_temporally_valid():
            return BacktestFoldResult(
                fold_number=fold.fold_number,
                evaluations=(),
                valid=False,
                notes=(
                    "Fold was rejected because its training and evaluation "
                    "periods are not temporally valid.",
                ),
            )

        fold_signals = tuple(
            signal
            for signal in signals
            if self._is_signal_in_evaluation_period(
                signal=signal,
                fold=fold,
            )
        )

        evaluations: list[TimeAwareEvaluation] = []

        for signal in fold_signals:
            observation = self._first_eligible_observation(
                signal=signal,
                observations=observations,
            )

            if observation is None:
                continue

            evaluations.append(
                self._analyzer.evaluate(
                    signal_id=signal.signal_id,
                    event_id=signal.event_id,
                    signal_created_at=signal.created_at,
                    observation=observation,
                ),
            )

        return BacktestFoldResult(
            fold_number=fold.fold_number,
            evaluations=tuple(evaluations),
            valid=True,
            notes=(
                f"{len(evaluations)} signal observations were evaluated for this fold.",
            ),
        )

    @staticmethod
    def _is_signal_in_evaluation_period(
        signal: BacktestSignal,
        fold: WalkForwardFold,
    ) -> bool:
        """Return whether a signal belongs to the fold's evaluation period."""

        return (
            fold.evaluation_period.start_at
            <= signal.created_at
            < fold.evaluation_period.end_at
        )

    @staticmethod
    def _first_eligible_observation(
        signal: BacktestSignal,
        observations: tuple[TimeAwareObservation, ...],
    ) -> TimeAwareObservation | None:
        """Return the earliest observation after a signal timestamp."""

        eligible_observations = [
            observation
            for observation in observations
            if (
                observation.instrument_id == signal.instrument_id
                and observation.observed_at > signal.created_at
            )
        ]

        if not eligible_observations:
            return None

        return min(
            eligible_observations,
            key=lambda observation: observation.observed_at,
        )

    @staticmethod
    def _build_notes(
        folds: tuple[WalkForwardFold, ...],
        fold_results: tuple[BacktestFoldResult, ...],
        evaluation_count: int,
    ) -> tuple[str, ...]:
        """Build execution-level notes."""

        if not folds:
            return ("No walk-forward folds were supplied for execution.",)

        valid_fold_count = sum(fold_result.valid for fold_result in fold_results)

        return (
            (f"{valid_fold_count} of {len(folds)} walk-forward folds were executable."),
            (f"{evaluation_count} signal-observation pairs were processed."),
            (
                "Each signal uses only the earliest observation strictly "
                "after its creation timestamp."
            ),
        )
