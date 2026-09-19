from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.portfolio.performance import PortfolioPerformanceService

USER_ID = uuid4()
PORTFOLIO_ID = uuid4()
USD_INSTRUMENT_ID = uuid4()
EUR_INSTRUMENT_ID = uuid4()


def day_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def make_position(
    *,
    instrument_id,
    currency: str,
    quantity: str,
    average_cost: str = "100",
    effective_at: datetime | None = None,
    symbol: str = "TEST",
):
    return SimpleNamespace(
        instrument_id=instrument_id,
        portfolio_id=PORTFOLIO_ID,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
        event_type="updated",
        effective_at=effective_at or day_end(date(2026, 1, 1)),
        symbol=symbol,
        name="Test Security",
        exchange="TEST",
        asset_class="equity",
        currency=currency,
        is_active=True,
    )


def make_state(
    observed_on: date,
    *,
    quantity: str,
    instrument_id=USD_INSTRUMENT_ID,
    currency: str = "USD",
    average_cost: str = "100",
    symbol: str = "TEST",
):
    return SimpleNamespace(
        as_of=day_end(observed_on),
        positions=(
            make_position(
                instrument_id=instrument_id,
                currency=currency,
                quantity=quantity,
                average_cost=average_cost,
                effective_at=day_end(observed_on),
                symbol=symbol,
            ),
        ),
    )


def make_bar(observed_on: date, close: str):
    return SimpleNamespace(
        timestamp=day_end(observed_on),
        close=Decimal(close),
        source="test",
    )


def make_cash_flow(
    *,
    amount: str,
    event_type: str,
    effective_at: datetime,
    currency: str = "USD",
    sequence_id: int = 1,
):
    return SimpleNamespace(
        sequence_id=sequence_id,
        currency=currency,
        amount=Decimal(amount),
        event_type=event_type,
        effective_at=effective_at,
    )


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return FakeScalarResult(self._values)


class FakeSession:
    def __init__(self, instrument_ids):
        self.instrument_ids = tuple(instrument_ids)

    async def execute(self, _statement):
        return FakeExecuteResult(self.instrument_ids)

    async def get(self, model, identifier):
        instrument_by_id = {
            USD_INSTRUMENT_ID: SimpleNamespace(
                id=USD_INSTRUMENT_ID,
                symbol="TEST",
                name="USD Test Security",
                exchange="TEST",
                asset_class="equity",
                currency="USD",
                is_active=True,
            ),
            EUR_INSTRUMENT_ID: SimpleNamespace(
                id=EUR_INSTRUMENT_ID,
                symbol="EUR1",
                name="EUR Test Security",
                exchange="TEST",
                asset_class="equity",
                currency="EUR",
                is_active=True,
            ),
        }

        return instrument_by_id.get(identifier)


class FakePersistence:
    def __init__(self, instrument_ids):
        self.session = FakeSession(instrument_ids)

    async def get_for_user(self, user_id, portfolio_id):
        assert user_id == USER_ID
        assert portfolio_id == PORTFOLIO_ID

        return (
            SimpleNamespace(
                id=PORTFOLIO_ID,
                name="Performance Test",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            1,
        )


class FakeMarketData:
    def __init__(self, bars_by_instrument):
        self.bars_by_instrument = bars_by_instrument

    async def get_historical_bars(
        self,
        instrument_id,
        start_at,
        end_at,
    ):
        assert start_at <= end_at
        return self.bars_by_instrument.get(instrument_id, ())


class FakeHistoricalStateService:
    def __init__(self, states):
        self.states = tuple(states)

    async def build_many(self, user_id, portfolio_id, *, as_ofs):
        assert user_id == USER_ID
        assert portfolio_id == PORTFOLIO_ID

        requested = set(as_ofs)

        return tuple(state for state in self.states if state.as_of in requested)


class FakeCashFlowPersistence:
    def __init__(self, cash_flows):
        self.cash_flows = tuple(cash_flows)
        self.calls = []

    async def list_for_user(
        self,
        user_id,
        portfolio_id,
        *,
        start_at=None,
        end_at=None,
        limit=None,
    ):
        assert user_id == USER_ID
        assert portfolio_id == PORTFOLIO_ID

        self.calls.append(
            {
                "start_at": start_at,
                "end_at": end_at,
                "limit": limit,
            },
        )

        return self.cash_flows


def make_service(
    *,
    states,
    bars_by_instrument,
    cash_flows=(),
    instrument_ids=(USD_INSTRUMENT_ID,),
):
    cash_flow_persistence = FakeCashFlowPersistence(cash_flows)

    service = PortfolioPerformanceService(
        persistence=FakePersistence(instrument_ids),
        market_data=FakeMarketData(bars_by_instrument),
        cash_flow_persistence=cash_flow_persistence,
    )

    service.historical_state = FakeHistoricalStateService(states)

    return service, cash_flow_persistence


def make_single_currency_bars(
    days,
    closes,
):
    return {
        USD_INSTRUMENT_ID: tuple(
            make_bar(day_value, close)
            for day_value, close in zip(days, closes, strict=True)
        ),
    }


@pytest.mark.asyncio
async def test_stable_holdings_keep_period_return_and_adjusted_return():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    service, cash_flow_persistence = make_service(
        states=tuple(
            make_state(
                day_value,
                quantity="1",
            )
            for day_value in days
        ),
        bars_by_instrument=make_single_currency_bars(
            days,
            ("100", "110", "120"),
        ),
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.period_return == Decimal("0.2")
    assert currency.external_cash_flow_adjusted_period_return == Decimal("0.2")
    assert currency.external_cash_flow_count == 0
    assert currency.external_net_cash_flow == Decimal("0")
    assert cash_flow_persistence.calls[0]["limit"] is None


@pytest.mark.asyncio
async def test_position_change_with_matching_external_deposit_exposes_adjusted_proxy():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    states = (
        make_state(days[0], quantity="1"),
        make_state(days[1], quantity="2"),
        make_state(days[2], quantity="2"),
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

    service, _cash_flow_persistence = make_service(
        states=states,
        bars_by_instrument=make_single_currency_bars(
            days,
            ("100", "100", "110"),
        ),
        cash_flows=cash_flows,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.period_return is None
    assert currency.external_cash_flow_adjusted_period_return == Decimal("0.2")
    assert currency.external_cash_flow_count == 1
    assert currency.external_net_cash_flow == Decimal("100")
    assert currency.quality == "insufficient"


@pytest.mark.asyncio
async def test_position_change_without_external_flow_has_no_adjusted_return():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    service, _cash_flow_persistence = make_service(
        states=(
            make_state(days[0], quantity="1"),
            make_state(days[1], quantity="2"),
            make_state(days[2], quantity="2"),
        ),
        bars_by_instrument=make_single_currency_bars(
            days,
            ("100", "100", "100"),
        ),
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.period_return is None
    assert currency.external_cash_flow_adjusted_period_return is None
    assert currency.external_cash_flow_count == 0
    assert currency.external_net_cash_flow == Decimal("0")


@pytest.mark.asyncio
async def test_cash_flow_at_first_observation_is_excluded():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
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

    service, _cash_flow_persistence = make_service(
        states=tuple(
            make_state(
                day_value,
                quantity="1",
            )
            for day_value in days
        ),
        bars_by_instrument=make_single_currency_bars(
            days,
            ("100", "120"),
        ),
        cash_flows=cash_flows,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.external_cash_flow_count == 0
    assert currency.external_net_cash_flow == Decimal("0")
    assert currency.external_cash_flow_adjusted_period_return == Decimal("0.2")


@pytest.mark.asyncio
async def test_cash_flow_at_last_observation_is_included():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
    )

    cash_flows = (
        make_cash_flow(
            amount="100",
            event_type="deposit",
            effective_at=day_end(days[-1]),
        ),
    )

    service, _cash_flow_persistence = make_service(
        states=(
            make_state(days[0], quantity="1"),
            make_state(days[1], quantity="2"),
        ),
        bars_by_instrument=make_single_currency_bars(
            days,
            ("100", "100"),
        ),
        cash_flows=cash_flows,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currency = result.currencies[0]

    assert currency.external_cash_flow_count == 1
    assert currency.external_net_cash_flow == Decimal("100")
    assert currency.external_cash_flow_adjusted_period_return == Decimal("0")


@pytest.mark.asyncio
async def test_cash_flow_currency_isolated_from_other_currency():
    days = (
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    states = (
        SimpleNamespace(
            as_of=day_end(days[0]),
            positions=(
                make_position(
                    instrument_id=USD_INSTRUMENT_ID,
                    currency="USD",
                    quantity="1",
                    effective_at=day_end(days[0]),
                ),
                make_position(
                    instrument_id=EUR_INSTRUMENT_ID,
                    currency="EUR",
                    quantity="1",
                    average_cost="50",
                    effective_at=day_end(days[0]),
                    symbol="EUR1",
                ),
            ),
        ),
        SimpleNamespace(
            as_of=day_end(days[1]),
            positions=(
                make_position(
                    instrument_id=USD_INSTRUMENT_ID,
                    currency="USD",
                    quantity="2",
                    effective_at=day_end(days[1]),
                ),
                make_position(
                    instrument_id=EUR_INSTRUMENT_ID,
                    currency="EUR",
                    quantity="1",
                    average_cost="50",
                    effective_at=day_end(days[1]),
                    symbol="EUR1",
                ),
            ),
        ),
        SimpleNamespace(
            as_of=day_end(days[2]),
            positions=(
                make_position(
                    instrument_id=USD_INSTRUMENT_ID,
                    currency="USD",
                    quantity="2",
                    effective_at=day_end(days[2]),
                ),
                make_position(
                    instrument_id=EUR_INSTRUMENT_ID,
                    currency="EUR",
                    quantity="1",
                    average_cost="50",
                    effective_at=day_end(days[2]),
                    symbol="EUR1",
                ),
            ),
        ),
    )

    bars_by_instrument = {
        USD_INSTRUMENT_ID: tuple(
            make_bar(day_value, close)
            for day_value, close in zip(
                days,
                ("100", "100", "110"),
                strict=True,
            )
        ),
        EUR_INSTRUMENT_ID: tuple(
            make_bar(day_value, close)
            for day_value, close in zip(
                days,
                ("50", "55", "60"),
                strict=True,
            )
        ),
    }

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
            currency="USD",
        ),
    )

    service, _cash_flow_persistence = make_service(
        states=states,
        bars_by_instrument=bars_by_instrument,
        cash_flows=cash_flows,
        instrument_ids=(
            USD_INSTRUMENT_ID,
            EUR_INSTRUMENT_ID,
        ),
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=day_end(days[-1]),
        lookback_days=10,
    )

    currencies = {item.currency: item for item in result.currencies}

    assert currencies["USD"].external_cash_flow_count == 1
    assert currencies["USD"].external_net_cash_flow == Decimal("100")
    assert currencies["USD"].external_cash_flow_adjusted_period_return == Decimal("0.2")

    assert currencies["EUR"].external_cash_flow_count == 0
    assert currencies["EUR"].external_net_cash_flow == Decimal("0")
    assert currencies["EUR"].period_return == Decimal("0.2")


def test_position_change_detection_ignores_provenance_timestamps():
    first_day = date(2026, 1, 1)
    second_day = date(2026, 1, 2)

    first_position = make_position(
        instrument_id=USD_INSTRUMENT_ID,
        currency="USD",
        quantity="1",
        effective_at=day_end(first_day),
    )

    second_position = make_position(
        instrument_id=USD_INSTRUMENT_ID,
        currency="USD",
        quantity="1",
        effective_at=day_end(second_day),
    )

    states = (
        SimpleNamespace(
            as_of=day_end(first_day),
            positions=(first_position,),
        ),
        SimpleNamespace(
            as_of=day_end(second_day),
            positions=(second_position,),
        ),
    )

    assert (
        PortfolioPerformanceService._has_position_change_after_first_observation(
            currency="USD",
            first_observed_on=first_day,
            last_observed_on=second_day,
            historical_states=states,
        )
        is False
    )
