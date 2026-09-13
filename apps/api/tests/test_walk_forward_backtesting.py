from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.backtesting.models import BacktestPeriod
from app.backtesting.service import WalkForwardBacktestService


def make_period(
    start_year: int,
    end_year: int,
) -> BacktestPeriod:
    """Create a yearly backtest period."""

    return BacktestPeriod(
        start_at=datetime(start_year, 1, 1, tzinfo=UTC),
        end_at=datetime(end_year, 1, 1, tzinfo=UTC),
    )


def test_creates_matching_walk_forward_folds() -> None:
    service = WalkForwardBacktestService()

    training_periods = (
        make_period(2020, 2021),
        make_period(2021, 2022),
    )
    evaluation_periods = (
        make_period(2022, 2023),
        make_period(2023, 2024),
    )

    folds = service.create_folds(
        training_periods=training_periods,
        evaluation_periods=evaluation_periods,
    )

    assert len(folds) == 2
    assert folds[0].fold_number == 1
    assert folds[1].fold_number == 2
    assert folds[0].is_temporally_valid() is True
    assert folds[1].is_temporally_valid() is True


def test_rejects_mismatched_period_counts() -> None:
    service = WalkForwardBacktestService()

    with pytest.raises(ValueError, match="same length"):
        service.create_folds(
            training_periods=(make_period(2020, 2021),),
            evaluation_periods=(
                make_period(2021, 2022),
                make_period(2022, 2023),
            ),
        )


def test_validates_temporally_ordered_folds() -> None:
    service = WalkForwardBacktestService()

    folds = service.create_folds(
        training_periods=(
            make_period(2020, 2021),
            make_period(2021, 2022),
        ),
        evaluation_periods=(
            make_period(2021, 2022),
            make_period(2022, 2023),
        ),
    )

    result = service.validate(
        folds,
        backtest_id=uuid4(),
    )

    assert result.valid is True
    assert result.invalid_fold_numbers == ()
    assert len(result.folds) == 2
    assert "passed temporal validation" in result.notes[0]


def test_rejects_evaluation_period_before_training_end() -> None:
    service = WalkForwardBacktestService()

    folds = service.create_folds(
        training_periods=(make_period(2020, 2021),),
        evaluation_periods=(make_period(2020, 2021),),
    )

    result = service.validate(folds)

    assert result.valid is False
    assert result.invalid_fold_numbers == (1,)
    assert "failed temporal validation" in result.notes[0]


def test_rejects_backward_fold_order() -> None:
    service = WalkForwardBacktestService()

    folds = service.create_folds(
        training_periods=(
            make_period(2021, 2022),
            make_period(2020, 2021),
        ),
        evaluation_periods=(
            make_period(2022, 2023),
            make_period(2021, 2022),
        ),
    )

    result = service.validate(folds)

    assert result.valid is False
    assert result.invalid_fold_numbers == ()
    assert any("not monotonically ordered" in note for note in result.notes)


def test_validates_empty_fold_set() -> None:
    result = WalkForwardBacktestService().validate(())

    assert result.valid is True
    assert result.invalid_fold_numbers == ()
    assert result.folds == ()
    assert result.notes == ("No walk-forward folds were supplied.",)
