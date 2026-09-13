from uuid import UUID, uuid4

from app.backtesting.models import (
    BacktestPeriod,
    WalkForwardFold,
    WalkForwardResult,
)


class WalkForwardBacktestAnalyzer:
    """Validate chronological walk-forward backtest folds."""

    def create_folds(
        self,
        training_periods: tuple[BacktestPeriod, ...],
        evaluation_periods: tuple[BacktestPeriod, ...],
    ) -> tuple[WalkForwardFold, ...]:
        """Create paired walk-forward folds from chronological periods."""

        if len(training_periods) != len(evaluation_periods):
            raise ValueError(
                "Training and evaluation periods must have the same length.",
            )

        return tuple(
            WalkForwardFold(
                fold_number=index,
                training_period=training_period,
                evaluation_period=evaluation_period,
            )
            for index, (training_period, evaluation_period) in enumerate(
                zip(
                    training_periods,
                    evaluation_periods,
                    strict=True,
                ),
                start=1,
            )
        )

    def validate(
        self,
        folds: tuple[WalkForwardFold, ...],
        backtest_id: UUID | None = None,
    ) -> WalkForwardResult:
        """Validate all walk-forward folds for temporal correctness."""

        invalid_fold_numbers = tuple(
            fold.fold_number for fold in folds if not fold.is_temporally_valid()
        )

        folds_are_ordered = self._folds_are_ordered(folds)

        valid = not invalid_fold_numbers and folds_are_ordered

        notes = self._build_notes(
            folds=folds,
            invalid_fold_numbers=invalid_fold_numbers,
            folds_are_ordered=folds_are_ordered,
            valid=valid,
        )

        return WalkForwardResult(
            backtest_id=backtest_id or uuid4(),
            folds=folds,
            valid=valid,
            invalid_fold_numbers=invalid_fold_numbers,
            notes=notes,
        )

    @staticmethod
    def _folds_are_ordered(
        folds: tuple[WalkForwardFold, ...],
    ) -> bool:
        """Ensure later folds do not move backward in time."""

        if len(folds) < 2:
            return True

        for previous, current in zip(
            folds,
            folds[1:],
            strict=False,
        ):
            if current.training_period.start_at < previous.training_period.start_at:
                return False

            if current.evaluation_period.start_at < previous.evaluation_period.start_at:
                return False

        return True

    @staticmethod
    def _build_notes(
        folds: tuple[WalkForwardFold, ...],
        invalid_fold_numbers: tuple[int, ...],
        folds_are_ordered: bool,
        valid: bool,
    ) -> tuple[str, ...]:
        """Build notes describing walk-forward temporal validation."""

        if not folds:
            return ("No walk-forward folds were supplied.",)

        if valid:
            return (
                f"{len(folds)} walk-forward folds passed temporal validation.",
                (
                    "Each evaluation period begins at or after the end of "
                    "its corresponding training period."
                ),
                (
                    "Fold ordering prevents later observations from being "
                    "used in earlier evaluation periods."
                ),
            )

        notes = [
            (
                f"{len(invalid_fold_numbers)} of {len(folds)} folds failed "
                "temporal validation."
            ),
        ]

        if invalid_fold_numbers:
            notes.append(
                (
                    "Invalid folds: "
                    + ", ".join(str(number) for number in invalid_fold_numbers)
                    + "."
                ),
            )

        if not folds_are_ordered:
            notes.append(
                "Fold chronology is not monotonically ordered.",
            )

        notes.append(
            "Invalid temporal folds must not be used for performance evaluation.",
        )

        return tuple(notes)
