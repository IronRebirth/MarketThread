from datetime import UTC, datetime
from uuid import uuid4

from app.backtesting.engine import BacktestSignal
from app.backtesting.models import BacktestPeriod, TimeAwareObservation
from app.backtesting.report_service import BacktestPerformanceReportService
from app.backtesting.service import (
    BacktestExecutionService,
    WalkForwardBacktestService,
)
from app.evaluation.models import (
    EvaluationRecommendationState,
    EvaluationSignalStrength,
)


def make_period(
    start_year: int,
    end_year: int,
) -> BacktestPeriod:
    """Create a yearly backtest period."""

    return BacktestPeriod(
        start_at=datetime(
            start_year,
            1,
            1,
            tzinfo=UTC,
        ),
        end_at=datetime(
            end_year,
            1,
            1,
            tzinfo=UTC,
        ),
    )


def make_signal(
    *,
    created_at: datetime,
    instrument_id,
    strength: EvaluationSignalStrength,
    recommendation: EvaluationRecommendationState,
) -> BacktestSignal:
    """Create a historical signal."""

    return BacktestSignal(
        signal_id=uuid4(),
        event_id=uuid4(),
        instrument_id=instrument_id,
        created_at=created_at,
        signal_strength=strength,
        recommendation_state=recommendation,
        confidence=0.84,
    )


def make_observation(
    *,
    observed_at: datetime,
    instrument_id,
    forward_return_pct: float,
    benchmark_return_pct: float,
) -> TimeAwareObservation:
    """Create a historical market observation."""

    return TimeAwareObservation(
        instrument_id=instrument_id,
        observed_at=observed_at,
        forward_return_pct=forward_return_pct,
        benchmark_return_pct=benchmark_return_pct,
    )


def execute_backtest():
    """Create a small executable backtest fixture."""

    instrument_id = uuid4()

    folds = WalkForwardBacktestService().create_folds(
        training_periods=(make_period(2020, 2021),),
        evaluation_periods=(make_period(2021, 2022),),
    )

    signals = (
        make_signal(
            created_at=datetime(
                2021,
                2,
                1,
                tzinfo=UTC,
            ),
            instrument_id=instrument_id,
            strength=EvaluationSignalStrength.STRONG,
            recommendation=EvaluationRecommendationState.CONSIDER,
        ),
        make_signal(
            created_at=datetime(
                2021,
                4,
                1,
                tzinfo=UTC,
            ),
            instrument_id=instrument_id,
            strength=EvaluationSignalStrength.MODERATE,
            recommendation=EvaluationRecommendationState.WATCH,
        ),
    )

    observations = (
        make_observation(
            observed_at=datetime(
                2021,
                2,
                5,
                tzinfo=UTC,
            ),
            instrument_id=instrument_id,
            forward_return_pct=5.0,
            benchmark_return_pct=1.0,
        ),
        make_observation(
            observed_at=datetime(
                2021,
                4,
                5,
                tzinfo=UTC,
            ),
            instrument_id=instrument_id,
            forward_return_pct=-2.0,
            benchmark_return_pct=1.0,
        ),
    )

    return BacktestExecutionService().execute(
        folds=folds,
        signals=signals,
        observations=observations,
    )


def test_builds_overall_performance_report() -> None:
    execution = execute_backtest()

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert report.backtest_id == str(execution.backtest_id)
    assert report.total_evaluations == 2
    assert report.valid_evaluations == 2
    assert report.rejected_evaluations == 0
    assert report.directional_accuracy is None
    assert report.average_forward_return_pct == 1.5
    assert report.average_relative_return_pct == 0.5
    assert report.positive_outcome_rate == 0.5


def test_report_contains_horizon_breakdown() -> None:
    execution = execute_backtest()

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert len(report.by_horizon.summaries) == 3


def test_report_contains_signal_strength_breakdown() -> None:
    execution = execute_backtest()

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert len(report.by_signal_strength.summaries) == 4

    strong = next(
        item
        for item in report.by_signal_strength.summaries
        if item.state == EvaluationSignalStrength.STRONG
    )
    moderate = next(
        item
        for item in report.by_signal_strength.summaries
        if item.state == EvaluationSignalStrength.MODERATE
    )

    assert strong.evaluation_count == 1
    assert moderate.evaluation_count == 1


def test_report_contains_recommendation_breakdown() -> None:
    execution = execute_backtest()

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert len(report.by_recommendation_state.summaries) == 5

    consider = next(
        item
        for item in report.by_recommendation_state.summaries
        if item.state == EvaluationRecommendationState.CONSIDER
    )
    watch = next(
        item
        for item in report.by_recommendation_state.summaries
        if item.state == EvaluationRecommendationState.WATCH
    )

    assert consider.evaluation_count == 1
    assert watch.evaluation_count == 1


def test_empty_execution_produces_explicit_report() -> None:
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

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert report.total_evaluations == 0
    assert report.valid_evaluations == 0
    assert report.directional_accuracy is None
    assert report.average_forward_return_pct is None
    assert report.average_relative_return_pct is None
    assert report.positive_outcome_rate is None
    assert "no evaluations" in report.notes[0].lower()


def test_report_exposes_server_side_market_data_quality() -> None:
    execution = execute_backtest().model_copy(
        update={
            "market_data_expected_count": 10,
            "market_data_resolved_count": 8,
            "market_data_coverage_ratio": 0.8,
        },
    )

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert report.market_data_quality_state == "insufficient"
    assert report.market_data_expected_count == 10
    assert report.market_data_resolved_count == 8
    assert report.market_data_coverage_ratio == 0.8
    assert report.market_data_quality_warnings == (
        "Market-data coverage is below the 95% minimum threshold.",
    )


def test_report_marks_market_data_as_not_assessed_for_manual_execution() -> None:
    execution = execute_backtest()

    report = BacktestPerformanceReportService().build_report(
        execution,
    )

    assert report.market_data_quality_state == "not_assessed"
    assert report.market_data_expected_count is None
    assert report.market_data_resolved_count is None
    assert report.market_data_coverage_ratio is None
