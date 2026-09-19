from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.portfolio.history_models import PortfolioHistoricalPosition
from app.portfolio.risk_metrics import (
    ANNUALIZATION_FACTOR,
    PortfolioRiskMetricsService,
    _build_segmented_drawdown,
    _build_segmented_returns,
    _CurrencyObservation,
)

USER_ID = uuid4()
PORTFOLIO_ID = uuid4()
INSTRUMENT_ID = uuid4()


def day_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def make_observation(
    observed_on: date,
    value: str,
    *,
    segment_id: int = 0,
) -> _CurrencyObservation:
    return _CurrencyObservation(
        observed_on=observed_on,
        value=Decimal(value),
        state_signature=((INSTRUMENT_ID, Decimal("1")),),
        segment_id=segment_id,
    )


def make_cash_flow(
    *,
    amount: str,
    event_type: str,
    effective_at: datetime,
    currency: str = "USD",
):
    return SimpleNamespace(
        currency=currency,
        amount=Decimal(amount),
        event_type=event_type,
        effective_at=effective_at,
        sequence_id=1,
    )


def make_position(
    observed_on: date,
    quantity: str = "1",
) -> PortfolioHistoricalPosition:
    return PortfolioHistoricalPosition(
        history_sequence_id=1,
        portfolio_id=PORTFOLIO_ID,
        instrument_id=INSTRUMENT_ID,
        quantity=Decimal(quantity),
        average_cost=Decimal("100"),
        event_type="updated",
        effective_at=day_end(observed_on),
        symbol="TEST",
        name="Risk Test Security",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )


def make_bar(
    observed_on: date,
    close: str,
):
    return SimpleNamespace(
        timestamp=day_end(observed_on),
        close=Decimal(close),
        source="risk-cash-flow-test",
    )


def test_external_deposit_is_removed_from_volatility_return_series():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    observations = (
        make_observation(days[0], "100"),
        make_observation(days[1], "210"),
        make_observation(days[2], "230"),
    )

    cash_flows = (
        make_cash_flow(
            amount="100",
            event_type="deposit",
            effective_at=datetime(
                2026,
                1,
                2,
                12,
                tzinfo=UTC,
            ),
        ),
    )

    returns = _build_segmented_returns(
        observations,
        cash_flows,
    )

    assert returns == pytest.approx(
        (
            0.1,
            0.18181818181818182,
        ),
        rel=1e-9,
    )

    expected_volatility = (
        (
            (
                (
                    0.1
                    - (
                        0.1
                        + float(
                            Decimal("130") / Decimal("110") - Decimal("1"),
                        )
                    )
                    / 2
                )
                ** 2
                + (
                    float(
                        Decimal("130") / Decimal("110") - Decimal("1"),
                    )
                    - (
                        0.1
                        + float(
                            Decimal("130") / Decimal("110") - Decimal("1"),
                        )
                    )
                    / 2
                )
                ** 2
            )
            / 1
        )
        ** 0.5
    ) * (ANNUALIZATION_FACTOR**0.5)

    actual_volatility = PortfolioRiskMetricsService._build_currency_metric(
        currency="USD",
        observations=observations,
        position_count=1,
        sources=(),
        cash_flows=cash_flows,
    ).annualized_volatility

    assert actual_volatility == pytest.approx(
        expected_volatility,
        rel=1e-9,
    )


def test_external_withdrawal_is_removed_from_drawdown():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    observations = (
        make_observation(days[0], "100"),
        make_observation(days[1], "50"),
        make_observation(days[2], "100"),
    )

    cash_flows = (
        make_cash_flow(
            amount="50",
            event_type="withdrawal",
            effective_at=datetime(
                2026,
                1,
                2,
                12,
                tzinfo=UTC,
            ),
        ),
    )

    drawdown, peak_on, trough_on = _build_segmented_drawdown(
        observations,
        cash_flows,
    )

    assert drawdown == pytest.approx(0.0)
    assert peak_on == days[0]
    assert trough_on == days[0]


def test_cash_flow_adjustment_does_not_cross_holding_state_boundaries():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 4),
    )

    observations = (
        make_observation(days[0], "100", segment_id=0),
        make_observation(days[1], "210", segment_id=0),
        make_observation(days[2], "180", segment_id=1),
        make_observation(days[3], "218", segment_id=1),
    )

    cash_flows = (
        make_cash_flow(
            amount="100",
            event_type="deposit",
            effective_at=datetime(
                2026,
                1,
                2,
                12,
                tzinfo=UTC,
            ),
        ),
        make_cash_flow(
            amount="38",
            event_type="deposit",
            effective_at=datetime(
                2026,
                1,
                4,
                12,
                tzinfo=UTC,
            ),
        ),
    )

    returns = _build_segmented_returns(
        observations,
        cash_flows,
    )

    assert len(returns) == 2
    assert returns[0] == pytest.approx(0.1)
    assert returns[1] == pytest.approx(0.0)


def test_first_observation_flow_is_excluded_from_adjustment_boundary():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
    )

    observations = (
        make_observation(days[0], "100"),
        make_observation(days[1], "140"),
    )

    cash_flows = (
        make_cash_flow(
            amount="100",
            event_type="deposit",
            effective_at=datetime(
                2026,
                1,
                1,
                12,
                tzinfo=UTC,
            ),
        ),
    )

    returns = _build_segmented_returns(
        observations,
        cash_flows,
    )

    assert returns == pytest.approx((0.4,))


@pytest.mark.asyncio
async def test_risk_service_uses_persisted_external_cash_flows():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    portfolio_record = SimpleNamespace(
        id=PORTFOLIO_ID,
        name="Cash Flow Risk Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    history_record = SimpleNamespace(
        instrument_id=INSTRUMENT_ID,
        recorded_at=datetime(
            2026,
            1,
            1,
            12,
            tzinfo=UTC,
        ),
    )

    class FakePersistence:
        async def get_detail_for_user(self, user_id, portfolio_id):
            assert user_id == USER_ID
            assert portfolio_id == PORTFOLIO_ID
            return portfolio_record, 1, ()

        async def list_position_history_for_window(
            self,
            *,
            user_id,
            portfolio_id,
            start_at,
            end_at,
        ):
            assert user_id == USER_ID
            assert portfolio_id == PORTFOLIO_ID
            return (history_record,)

    class FakeMarketData:
        async def get_historical_bars(
            self,
            instrument_id,
            start_at,
            end_at,
        ):
            assert instrument_id == INSTRUMENT_ID
            return (
                make_bar(days[0], "100"),
                make_bar(days[1], "210"),
                make_bar(days[2], "198"),
            )

    states = tuple(
        SimpleNamespace(
            as_of=day_end(day_value),
            positions=(make_position(day_value),),
        )
        for day_value in days
    )

    class FakeHistoricalStateService:
        async def build_many(
            self,
            user_id,
            portfolio_id,
            *,
            as_ofs,
        ):
            assert user_id == USER_ID
            assert portfolio_id == PORTFOLIO_ID

            return tuple(state for state in states if state.as_of in as_ofs)

    class FakeCashFlowPersistence:
        async def list_for_user(
            self,
            user_id,
            portfolio_id,
            *,
            start_at,
            end_at,
            limit,
        ):
            assert user_id == USER_ID
            assert portfolio_id == PORTFOLIO_ID
            assert limit is None

            return (
                make_cash_flow(
                    amount="100",
                    event_type="deposit",
                    effective_at=datetime(
                        2026,
                        1,
                        2,
                        12,
                        tzinfo=UTC,
                    ),
                ),
            )

    service = PortfolioRiskMetricsService(
        persistence=FakePersistence(),
        market_data=FakeMarketData(),
        cash_flow_persistence=FakeCashFlowPersistence(),
    )
    service.historical_state = FakeHistoricalStateService()

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.quality == "sufficient"
    assert currency.return_count == 2
    assert currency.annualized_volatility is not None
    assert currency.maximum_drawdown == pytest.approx(
        98 / 110 - 1,
    )
    assert any(
        "Recorded external cash flows after the first complete observation" in note
        for note in currency.notes
    )
    assert any(
        "Holding-state changes remain segmentation boundaries" in note
        for note in currency.notes
    )
