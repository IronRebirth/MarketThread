import pytest

from app.backtesting.horizon import BacktestHorizon
from app.backtesting.market_data_quality import (
    assess_market_data_horizon_quality,
    build_market_data_horizon_quality,
)


def test_assesses_sufficient_market_data_coverage() -> None:
    result = assess_market_data_horizon_quality(
        horizon=BacktestHorizon.ONE_DAY,
        expected_count=100,
        resolved_count=100,
    )

    assert result.horizon == BacktestHorizon.ONE_DAY
    assert result.expected_count == 100
    assert result.resolved_count == 100
    assert result.coverage_ratio == 1.0
    assert result.quality_state == "sufficient"
    assert result.warnings == ()


def test_assesses_insufficient_market_data_coverage() -> None:
    result = assess_market_data_horizon_quality(
        horizon=BacktestHorizon.FIVE_DAYS,
        expected_count=100,
        resolved_count=50,
    )

    assert result.horizon == BacktestHorizon.FIVE_DAYS
    assert result.coverage_ratio == 0.5
    assert result.quality_state == "insufficient"
    assert result.warnings


def test_assesses_unavailable_market_data_when_no_signals_exist() -> None:
    result = assess_market_data_horizon_quality(
        horizon=BacktestHorizon.TWENTY_DAYS,
        expected_count=0,
        resolved_count=0,
    )

    assert result.coverage_ratio is None
    assert result.quality_state == "unavailable"
    assert result.warnings


def test_rejects_negative_expected_count() -> None:
    with pytest.raises(
        ValueError,
        match="expected_count must be non-negative",
    ):
        assess_market_data_horizon_quality(
            horizon=BacktestHorizon.ONE_DAY,
            expected_count=-1,
            resolved_count=0,
        )


def test_rejects_negative_resolved_count() -> None:
    with pytest.raises(
        ValueError,
        match="resolved_count must be non-negative",
    ):
        assess_market_data_horizon_quality(
            horizon=BacktestHorizon.ONE_DAY,
            expected_count=1,
            resolved_count=-1,
        )


def test_rejects_resolved_count_above_expected_count() -> None:
    with pytest.raises(
        ValueError,
        match="resolved_count cannot exceed expected_count",
    ):
        assess_market_data_horizon_quality(
            horizon=BacktestHorizon.ONE_DAY,
            expected_count=1,
            resolved_count=2,
        )


def test_builds_assessments_for_all_supported_horizons() -> None:
    result = build_market_data_horizon_quality(
        expected_by_horizon={
            BacktestHorizon.ONE_DAY: 10,
            BacktestHorizon.FIVE_DAYS: 20,
        },
        resolved_by_horizon={
            BacktestHorizon.ONE_DAY: 10,
            BacktestHorizon.FIVE_DAYS: 10,
        },
    )

    assert tuple(item.horizon for item in result) == (
        BacktestHorizon.ONE_DAY,
        BacktestHorizon.FIVE_DAYS,
        BacktestHorizon.TWENTY_DAYS,
    )

    one_day = result[0]
    five_days = result[1]
    twenty_days = result[2]

    assert one_day.quality_state == "sufficient"
    assert one_day.coverage_ratio == 1.0

    assert five_days.quality_state == "insufficient"
    assert five_days.coverage_ratio == 0.5

    assert twenty_days.quality_state == "unavailable"
    assert twenty_days.coverage_ratio is None
