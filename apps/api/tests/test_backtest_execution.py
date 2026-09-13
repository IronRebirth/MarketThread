from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.models import (
    BacktestPeriod,
    BacktestStatus,
    TimeAwareObservation,
)
from app.backtesting.service import (
    BacktestExecutionService,
    WalkForwardBacktestService,
)


def make_period(
    start_year: int,
    end_year: int,
) -> BacktestPeriod:
    """Create a yearly backtest period."""

    return BacktestPeriod(
        start_at=datetime(start_year, 1, 1, tzinfo=UTC),
        end_at=datetime(end_year, 1, 1, tzinfo=UTC),
    )


def make_signal(
    *,
    created_at: datetime,
    instrument_id: UUID,
) -> BacktestSignal:
    """Create a historical signal."""

    return BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=created_at,
    )


def make_observation(
    *,
    observed_at: datetime,
    instrument_id: UUID,
    forward_return_pct: float = 5.0,
    benchmark_return_pct: float = 1.0,
) -> TimeAwareObservation:
    """Create a historical market observation."""

    return TimeAwareObservation(
        instrument_id=instrument_id,
        observed_at=observed_at,
        forward_return_pct=forward_return_pct,
        benchmark_return_pct=benchmark_return_pct,
    )


def make_valid_fold():
    """Create one valid walk-forward fold."""

    service = WalkForwardBacktestService()

    return service.create_folds(
        training_periods=(make_period(2020, 2021),),
        evaluation_periods=(make_period(2021, 2022),),
    )


def test_executes_signal_against_forward_observation() -> None:
    instrument_id = uuid4()
    signal_created_at = datetime(2021, 2, 1, tzinfo=UTC)
    observed_at = datetime(2021, 2, 5, tzinfo=UTC)

    folds = make_valid_fold()

    signal = make_signal(
        created_at=signal_created_at,
        instrument_id=instrument_id,
    )
    observation = make_observation(
        observed_at=observed_at,
        instrument_id=instrument_id,
    )

    result = BacktestExecutionService().execute(
        folds=folds,
        signals=(signal,),
        observations=(observation,),
    )

    assert result.valid is True
    assert result.evaluation_count == 1
    assert result.valid_evaluation_count == 1
    assert result.rejected_evaluation_count == 0
    assert len(result.fold_results) == 1
    assert result.fold_results[0].evaluations[0].status == BacktestStatus.VALID


def test_does_not_use_observation_before_signal() -> None:
    instrument_id = uuid4()
    signal_created_at = datetime(2021, 6, 1, tzinfo=UTC)
    observed_at = datetime(2021, 5, 31, tzinfo=UTC)

    folds = make_valid_fold()

    signal = make_signal(
        created_at=signal_created_at,
        instrument_id=instrument_id,
    )
    observation = make_observation(
        observed_at=observed_at,
        instrument_id=instrument_id,
    )

    result = BacktestExecutionService().execute(
        folds=folds,
        signals=(signal,),
        observations=(observation,),
    )

    assert result.evaluation_count == 0
    assert result.valid_evaluation_count == 0


def test_ignores_signals_outside_evaluation_period() -> None:
    instrument_id = uuid4()
    signal_created_at = datetime(2020, 6, 1, tzinfo=UTC)
    observed_at = datetime(2020, 6, 5, tzinfo=UTC)

    folds = make_valid_fold()

    signal = make_signal(
        created_at=signal_created_at,
        instrument_id=instrument_id,
    )
    observation = make_observation(
        observed_at=observed_at,
        instrument_id=instrument_id,
    )

    result = BacktestExecutionService().execute(
        folds=folds,
        signals=(signal,),
        observations=(observation,),
    )

    assert result.evaluation_count == 0
    assert result.valid_evaluation_count == 0


def test_executes_multiple_signals_with_one_observation_each() -> None:
    instrument_id = uuid4()

    signals = (
        make_signal(
            created_at=datetime(2021, 2, 1, tzinfo=UTC),
            instrument_id=instrument_id,
        ),
        make_signal(
            created_at=datetime(2021, 4, 1, tzinfo=UTC),
            instrument_id=instrument_id,
        ),
    )

    observations = (
        make_observation(
            observed_at=datetime(2021, 2, 5, tzinfo=UTC),
            instrument_id=instrument_id,
        ),
        make_observation(
            observed_at=datetime(2021, 4, 5, tzinfo=UTC),
            instrument_id=instrument_id,
            forward_return_pct=3.0,
            benchmark_return_pct=1.0,
        ),
    )

    result = BacktestExecutionService().execute(
        folds=make_valid_fold(),
        signals=signals,
        observations=observations,
    )

    assert result.evaluation_count == 2


def test_uses_earliest_eligible_observation() -> None:
    instrument_id = uuid4()

    signal = make_signal(
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        instrument_id=instrument_id,
    )

    observations = (
        make_observation(
            observed_at=datetime(2021, 2, 10, tzinfo=UTC),
            instrument_id=instrument_id,
            forward_return_pct=10.0,
        ),
        make_observation(
            observed_at=datetime(2021, 2, 3, tzinfo=UTC),
            instrument_id=instrument_id,
            forward_return_pct=2.0,
        ),
    )

    result = BacktestExecutionService().execute(
        folds=make_valid_fold(),
        signals=(signal,),
        observations=observations,
    )

    evaluation = result.fold_results[0].evaluations[0]

    assert evaluation.observation.observed_at == datetime(
        2021,
        2,
        3,
        tzinfo=UTC,
    )
    assert evaluation.observation.forward_return_pct == 2.0


def test_rejects_invalid_fold_execution() -> None:
    service = WalkForwardBacktestService()

    folds = service.create_folds(
        training_periods=(make_period(2021, 2022),),
        evaluation_periods=(make_period(2020, 2021),),
    )

    result = BacktestExecutionService().execute(
        folds=folds,
        signals=(),
        observations=(),
    )

    assert result.valid is False
    assert result.evaluation_count == 0
    assert result.fold_results[0].valid is False


def test_empty_folds_produce_invalid_execution() -> None:
    result = BacktestExecutionService().execute(
        folds=(),
        signals=(),
        observations=(),
    )

    assert result.valid is False
    assert result.evaluation_count == 0
    assert result.valid_evaluation_count == 0
    assert result.rejected_evaluation_count == 0
