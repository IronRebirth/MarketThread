from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.backtesting.horizon import BacktestHorizon
from app.backtesting.models import BacktestPeriod, TimeAwareObservation
from app.backtesting.resolver import BacktestDataResolver


def make_period() -> BacktestPeriod:
    return BacktestPeriod(
        start_at=datetime(2021, 1, 1, tzinfo=UTC),
        end_at=datetime(2022, 1, 1, tzinfo=UTC),
    )


def make_signal_record(
    *,
    time_horizon: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        event_id=uuid4(),
        instrument_id=uuid4(),
        created_at=datetime(2021, 2, 1, tzinfo=UTC),
        direction="positive",
        strength="strong",
        opportunity="opportunity",
        confidence=0.9,
        time_horizon=time_horizon,
    )


@pytest.mark.asyncio
async def test_resolver_builds_per_horizon_market_data_quality(
    monkeypatch,
) -> None:
    one_day_signal = make_signal_record(
        time_horizon="short_term",
    )
    five_day_signal = make_signal_record(
        time_horizon="medium_term",
    )

    resolver = BacktestDataResolver()

    async def fake_load_signals(session, evaluation_periods):
        return (
            one_day_signal,
            five_day_signal,
        )

    async def fake_resolve_observations(
        session,
        signals,
        *,
        benchmark_instrument_id,
    ):
        observation = TimeAwareObservation(
            instrument_id=signals[0].instrument_id,
            observed_at=datetime(2021, 2, 2, tzinfo=UTC),
            forward_return_pct=2.0,
            benchmark_return_pct=None,
            horizon=BacktestHorizon.ONE_DAY,
        )

        return (observation,), 1

    monkeypatch.setattr(
        resolver,
        "_load_signals",
        fake_load_signals,
    )
    monkeypatch.setattr(
        resolver,
        "_resolve_observations",
        fake_resolve_observations,
    )

    result = await resolver.resolve(
        object(),
        evaluation_periods=(make_period(),),
    )

    assert result.market_data_expected_count == 2
    assert result.market_data_resolved_count == 1
    assert result.market_data_coverage_ratio == 0.5

    assert result.market_data_horizon_quality is not None

    quality = {item.horizon: item for item in result.market_data_horizon_quality}

    assert quality[BacktestHorizon.ONE_DAY].expected_count == 1
    assert quality[BacktestHorizon.ONE_DAY].resolved_count == 1
    assert quality[BacktestHorizon.ONE_DAY].coverage_ratio == 1.0
    assert quality[BacktestHorizon.ONE_DAY].quality_state == "sufficient"

    assert quality[BacktestHorizon.FIVE_DAYS].expected_count == 1
    assert quality[BacktestHorizon.FIVE_DAYS].resolved_count == 0
    assert quality[BacktestHorizon.FIVE_DAYS].coverage_ratio == 0.0
    assert quality[BacktestHorizon.FIVE_DAYS].quality_state == "insufficient"

    assert quality[BacktestHorizon.TWENTY_DAYS].expected_count == 0
    assert quality[BacktestHorizon.TWENTY_DAYS].resolved_count == 0
    assert quality[BacktestHorizon.TWENTY_DAYS].coverage_ratio is None
    assert quality[BacktestHorizon.TWENTY_DAYS].quality_state == "unavailable"
