from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.horizon import BacktestHorizon
from app.backtesting.market_data_quality import (
    BacktestMarketDataHorizonQuality,
)
from app.backtesting.models import (
    BacktestPeriod,
    TimeAwareObservation,
    WalkForwardFold,
)
from app.backtesting.report_service import BacktestPerformanceReportService
from app.backtesting.service import BacktestExecutionService


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


def test_report_keeps_market_data_quality_separate_from_evaluation_quality() -> None:
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
        market_data_expected_count=1,
        market_data_resolved_count=1,
        market_data_horizon_quality=(
            BacktestMarketDataHorizonQuality(
                horizon=BacktestHorizon.ONE_DAY,
                expected_count=1,
                resolved_count=1,
                coverage_ratio=1.0,
                quality_state="sufficient",
                warnings=(),
            ),
            BacktestMarketDataHorizonQuality(
                horizon=BacktestHorizon.FIVE_DAYS,
                expected_count=0,
                resolved_count=0,
                coverage_ratio=None,
                quality_state="unavailable",
                warnings=("No deterministic signals were available for this horizon.",),
            ),
            BacktestMarketDataHorizonQuality(
                horizon=BacktestHorizon.TWENTY_DAYS,
                expected_count=0,
                resolved_count=0,
                coverage_ratio=None,
                quality_state="unavailable",
                warnings=("No deterministic signals were available for this horizon.",),
            ),
        ),
    )

    report = BacktestPerformanceReportService().build_report(execution)

    summaries = {summary.state: summary for summary in report.by_horizon.summaries}

    one_day = summaries[BacktestHorizon.ONE_DAY]

    assert one_day.quality is not None
    assert one_day.market_data_quality is not None

    assert one_day.quality.state.value != one_day.market_data_quality.quality_state
    assert one_day.market_data_quality.expected_count == 1
    assert one_day.market_data_quality.resolved_count == 1
    assert one_day.market_data_quality.coverage_ratio == 1.0
    assert one_day.market_data_quality.quality_state == "sufficient"

    five_days = summaries[BacktestHorizon.FIVE_DAYS]

    assert five_days.market_data_quality is not None
    assert five_days.market_data_quality.quality_state == "unavailable"

    assert report.market_data_quality_by_horizon is not None
    assert len(report.market_data_quality_by_horizon) == 3
