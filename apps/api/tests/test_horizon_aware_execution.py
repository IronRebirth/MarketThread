from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import BacktestPeriod, TimeAwareObservation, WalkForwardFold
from app.backtesting.service import BacktestExecutionService
from app.evaluation.models import EvaluationDirection

UTC = UTC


def make_fold() -> tuple[WalkForwardFold, ...]:
    return (
        WalkForwardFold(
            fold_number=1,
            training_periods=(
                BacktestPeriod(
                    start_at=datetime(2020, 1, 1, tzinfo=UTC),
                    end_at=datetime(2021, 1, 1, tzinfo=UTC),
                ),
            ),
            evaluation_periods=(
                BacktestPeriod(
                    start_at=datetime(2021, 1, 1, tzinfo=UTC),
                    end_at=datetime(2022, 1, 1, tzinfo=UTC),
                ),
            ),
        ),
    )


def make_signal(instrument_id) -> BacktestSignal:
    return BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        direction=EvaluationDirection.POSITIVE,
        horizons=(
            BacktestHorizon.ONE_DAY,
            BacktestHorizon.FIVE_DAYS,
            BacktestHorizon.TWENTY_DAYS,
        ),
    )


def test_executes_one_evaluation_per_requested_horizon() -> None:
    instrument_id = uuid4()

    observations = (
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2021, 2, 2, tzinfo=UTC),
            forward_return_pct=1.0,
            benchmark_return_pct=0.5,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 8, tzinfo=UTC),
            forward_return_pct=3.0,
            benchmark_return_pct=1.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.TWENTY_DAYS,
            observed_at=datetime(2021, 2, 22, tzinfo=UTC),
            forward_return_pct=8.0,
            benchmark_return_pct=2.0,
        ),
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(make_signal(instrument_id),),
        observations=observations,
    )

    assert result.evaluation_count == 3
    assert len(result.horizon_evaluations) == 3

    horizons = {evaluation.horizon for evaluation in result.horizon_evaluations}

    assert horizons == {
        BacktestHorizon.ONE_DAY,
        BacktestHorizon.FIVE_DAYS,
        BacktestHorizon.TWENTY_DAYS,
    }


def test_horizons_use_their_matching_observations() -> None:
    instrument_id = uuid4()

    observations = (
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2021, 2, 2, tzinfo=UTC),
            forward_return_pct=2.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 8, tzinfo=UTC),
            forward_return_pct=5.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.TWENTY_DAYS,
            observed_at=datetime(2021, 2, 22, tzinfo=UTC),
            forward_return_pct=10.0,
        ),
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(make_signal(instrument_id),),
        observations=observations,
    )

    by_horizon = {
        evaluation.horizon: evaluation for evaluation in result.horizon_evaluations
    }

    assert by_horizon[BacktestHorizon.ONE_DAY].forward_return_pct == 2.0
    assert by_horizon[BacktestHorizon.FIVE_DAYS].forward_return_pct == 5.0
    assert by_horizon[BacktestHorizon.TWENTY_DAYS].forward_return_pct == 10.0


def test_missing_horizon_observation_is_skipped() -> None:
    instrument_id = uuid4()

    signal = BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        horizons=(
            BacktestHorizon.ONE_DAY,
            BacktestHorizon.FIVE_DAYS,
        ),
    )

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        horizon=BacktestHorizon.ONE_DAY,
        observed_at=datetime(2021, 2, 2, tzinfo=UTC),
        forward_return_pct=2.0,
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=(observation,),
    )

    assert result.evaluation_count == 1
    assert len(result.horizon_evaluations) == 1
    assert result.horizon_evaluations[0].horizon == BacktestHorizon.ONE_DAY


def test_legacy_signal_without_horizons_is_still_supported() -> None:
    instrument_id = uuid4()

    signal = BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
    )

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        observed_at=datetime(2021, 2, 5, tzinfo=UTC),
        forward_return_pct=4.0,
        benchmark_return_pct=1.0,
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=(observation,),
    )

    assert result.evaluation_count == 1
    assert len(result.evaluations) == 1
    assert result.evaluations[0].horizon is None


def test_horizon_execution_remains_time_aware() -> None:
    instrument_id = uuid4()

    signal = make_signal(instrument_id)

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        horizon=BacktestHorizon.ONE_DAY,
        observed_at=datetime(2021, 1, 31, tzinfo=UTC),
        forward_return_pct=4.0,
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=(observation,),
    )

    assert result.evaluation_count == 0


def test_earliest_matching_horizon_observation_is_selected() -> None:
    instrument_id = uuid4()

    signal = make_signal(instrument_id)

    observations = (
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 10, tzinfo=UTC),
            forward_return_pct=10.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 5, tzinfo=UTC),
            forward_return_pct=2.0,
        ),
    )

    result = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=observations,
    )

    five_day = next(
        evaluation
        for evaluation in result.horizon_evaluations
        if evaluation.horizon == BacktestHorizon.FIVE_DAYS
    )

    assert five_day.forward_return_pct == 2.0
