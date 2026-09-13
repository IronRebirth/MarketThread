from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import (
    BacktestPeriod,
    TimeAwareObservation,
    WalkForwardFold,
)
from app.backtesting.quality import BacktestQualityState
from app.backtesting.report_service import BacktestPerformanceReportService
from app.backtesting.service import BacktestExecutionService

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


def test_report_exposes_overall_quality() -> None:
    instrument_id = uuid4()

    signal = BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
    )

    observation = TimeAwareObservation(
        instrument_id=instrument_id,
        observed_at=datetime(2021, 2, 2, tzinfo=UTC),
        forward_return_pct=3.0,
        benchmark_return_pct=1.0,
    )

    execution = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=(observation,),
    )

    report = BacktestPerformanceReportService().build_report(execution)

    assert report.quality.evaluation_count == 1
    assert report.quality.state == BacktestQualityState.INSUFFICIENT_EVIDENCE


def test_report_marks_empty_execution_as_insufficient_evidence() -> None:
    from app.backtesting.engine import BacktestExecutionResult

    execution = BacktestExecutionResult(
        backtest_id=uuid4(),
        fold_results=(),
        valid=False,
        evaluation_count=0,
        valid_evaluation_count=0,
        rejected_evaluation_count=0,
        notes=(),
    )

    report = BacktestPerformanceReportService().build_report(execution)

    assert report.quality.state == BacktestQualityState.INSUFFICIENT_EVIDENCE
    assert report.quality.evaluation_count == 0


def test_horizon_summary_contains_its_own_quality_assessment() -> None:
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
            forward_return_pct=5.0,
            benchmark_return_pct=2.0,
        ),
    )

    execution = BacktestExecutionService().execute(
        folds=make_fold(),
        signals=(signal,),
        observations=observations,
    )

    report = BacktestPerformanceReportService().build_report(execution)

    summaries = {summary.state: summary for summary in report.by_horizon.summaries}

    assert summaries[BacktestHorizon.ONE_DAY].quality is not None
    assert (
        summaries[BacktestHorizon.ONE_DAY].quality.state
        == BacktestQualityState.INSUFFICIENT_EVIDENCE
    )

    assert summaries[BacktestHorizon.FIVE_DAYS].quality is not None
