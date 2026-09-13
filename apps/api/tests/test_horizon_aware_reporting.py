from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import (
    BacktestPeriod,
    TimeAwareObservation,
    WalkForwardFold,
)
from app.backtesting.report_service import BacktestPerformanceReportService
from app.backtesting.service import BacktestExecutionService
from app.evaluation.models import (
    EvaluationDirection,
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)

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


def test_report_uses_real_horizon_specific_evaluations() -> None:
    instrument_id = uuid4()

    signal = BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        direction=EvaluationDirection.POSITIVE,
        signal_strength=EvaluationSignalStrength.STRONG,
        recommendation_state=EvaluationRecommendationState.CONSIDER,
        confidence=0.9,
        horizons=(
            BacktestHorizon.ONE_DAY,
            BacktestHorizon.FIVE_DAYS,
            BacktestHorizon.TWENTY_DAYS,
        ),
    )

    observations = (
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2021, 2, 2, tzinfo=UTC),
            forward_return_pct=2.0,
            benchmark_return_pct=1.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 6, tzinfo=UTC),
            forward_return_pct=5.0,
            benchmark_return_pct=2.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.TWENTY_DAYS,
            observed_at=datetime(2021, 2, 22, tzinfo=UTC),
            forward_return_pct=10.0,
            benchmark_return_pct=4.0,
        ),
    )

    execution = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=observations,
    )

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert execution.evaluation_count == 3
    assert len(report.by_horizon.summaries) == 3

    summaries = {item.state: item for item in report.by_horizon.summaries}

    assert summaries[BacktestHorizon.ONE_DAY].average_forward_return_pct == 2.0
    assert summaries[BacktestHorizon.FIVE_DAYS].average_forward_return_pct == 5.0
    assert summaries[BacktestHorizon.TWENTY_DAYS].average_forward_return_pct == 10.0


def test_horizon_report_does_not_duplicate_overall_metrics_for_missing_horizons() -> (
    None
):
    instrument_id = uuid4()

    signal = BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        horizons=(BacktestHorizon.ONE_DAY,),
    )

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        horizon=BacktestHorizon.ONE_DAY,
        observed_at=datetime(2021, 2, 2, tzinfo=UTC),
        forward_return_pct=3.0,
        benchmark_return_pct=1.0,
    )

    execution = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=(observation,),
    )

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    summaries = {item.state: item for item in report.by_horizon.summaries}

    assert summaries[BacktestHorizon.ONE_DAY].evaluation_count == 1
    assert summaries[BacktestHorizon.ONE_DAY].average_forward_return_pct == 3.0

    assert summaries[BacktestHorizon.FIVE_DAYS].evaluation_count == 0
    assert summaries[BacktestHorizon.FIVE_DAYS].average_forward_return_pct is None

    assert summaries[BacktestHorizon.TWENTY_DAYS].evaluation_count == 0
    assert summaries[BacktestHorizon.TWENTY_DAYS].average_forward_return_pct is None


def test_overall_report_still_includes_horizon_evaluations() -> None:
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

    observations = (
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.ONE_DAY,
            observed_at=datetime(2021, 2, 2, tzinfo=UTC),
            forward_return_pct=2.0,
            benchmark_return_pct=1.0,
        ),
        TimeAwareObservation(
            instrument_id=instrument_id,
            horizon=BacktestHorizon.FIVE_DAYS,
            observed_at=datetime(2021, 2, 6, tzinfo=UTC),
            forward_return_pct=6.0,
            benchmark_return_pct=2.0,
        ),
    )

    execution = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=observations,
    )

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert report.total_evaluations == 2
    assert report.valid_evaluations == 2
    assert report.average_forward_return_pct == 4.0
    assert report.average_relative_return_pct == 2.5
