from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.portfolio.performance import PortfolioPerformanceService

ASSESSED_AT = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
PORTFOLIO_ID = uuid4()
USER_ID = uuid4()


def make_instrument(
    instrument_id: UUID,
    *,
    symbol: str,
    currency: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=instrument_id,
        symbol=symbol,
        name=f"{symbol} Holdings",
        exchange="TEST",
        asset_class="equity",
        currency=currency,
        is_active=True,
    )


def make_position_record(
    instrument_id: UUID,
    *,
    quantity: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        portfolio_id=PORTFOLIO_ID,
        instrument_id=instrument_id,
        quantity=Decimal(quantity),
        average_cost=Decimal("100"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_bar(
    observed_on: date,
    close: str,
    *,
    source: str = "test",
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=datetime(
            observed_on.year,
            observed_on.month,
            observed_on.day,
            16,
            0,
            tzinfo=UTC,
        ),
        close=Decimal(close),
        source=source,
    )


def make_detail(
    position_records: tuple[SimpleNamespace, ...],
) -> tuple[SimpleNamespace, int, tuple[SimpleNamespace, ...]]:
    portfolio = SimpleNamespace(
        id=PORTFOLIO_ID,
        name="Test Portfolio",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    return (
        portfolio,
        len(position_records),
        position_records,
    )


class FakeSession:
    def __init__(
        self,
        instruments: dict[UUID, SimpleNamespace],
    ) -> None:
        self.instruments = instruments

    async def get(
        self,
        _model: object,
        instrument_id: UUID,
    ) -> SimpleNamespace | None:
        return self.instruments.get(instrument_id)


class FakePersistence:
    def __init__(
        self,
        detail: tuple[SimpleNamespace, int, tuple[SimpleNamespace, ...]],
        instruments: dict[UUID, SimpleNamespace],
    ) -> None:
        self.detail = detail
        self.session = FakeSession(instruments)

    async def get_detail_for_user(
        self,
        _user_id: UUID,
        _portfolio_id: UUID,
    ) -> tuple[SimpleNamespace, int, tuple[SimpleNamespace, ...]]:
        return self.detail


class FakeMarketData:
    def __init__(
        self,
        histories: dict[UUID, tuple[SimpleNamespace, ...]],
    ) -> None:
        self.histories = histories

    async def get_historical_bars(
        self,
        instrument_id: UUID,
        _start_at: datetime,
        _end_at: datetime,
    ) -> tuple[SimpleNamespace, ...]:
        return self.histories.get(instrument_id, ())


def make_service(
    position_records: tuple[SimpleNamespace, ...],
    instruments: dict[UUID, SimpleNamespace],
    histories: dict[UUID, tuple[SimpleNamespace, ...]],
) -> PortfolioPerformanceService:
    persistence = FakePersistence(
        make_detail(position_records),
        instruments,
    )
    market_data = FakeMarketData(histories)

    return PortfolioPerformanceService(
        persistence,
        market_data,
    )


@pytest.mark.asyncio
async def test_builds_historical_values_and_period_return() -> None:
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="TEST",
        currency="USD",
    )
    position = make_position_record(
        instrument_id,
        quantity="2",
    )

    service = make_service(
        (position,),
        {instrument_id: instrument},
        {
            instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
                make_bar(date(2026, 1, 3), "120"),
            ),
        },
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    assert result.position_count == 1
    assert result.quality == "sufficient"
    assert len(result.currencies) == 1

    currency = result.currencies[0]

    assert currency.currency == "USD"
    assert currency.observation_count == 3
    assert currency.return_count == 2
    assert currency.initial_value == Decimal("200")
    assert currency.latest_value == Decimal("240")
    assert currency.period_return == Decimal("0.2")
    assert [point.value for point in currency.points] == [
        Decimal("200"),
        Decimal("220"),
        Decimal("240"),
    ]
    assert [point.observed_on for point in currency.points] == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]


@pytest.mark.asyncio
async def test_keeps_multiple_currencies_separate() -> None:
    usd_instrument_id = uuid4()
    eur_instrument_id = uuid4()

    usd_position = make_position_record(
        usd_instrument_id,
        quantity="1",
    )
    eur_position = make_position_record(
        eur_instrument_id,
        quantity="1",
    )

    instruments = {
        usd_instrument_id: make_instrument(
            usd_instrument_id,
            symbol="USDSTK",
            currency="USD",
        ),
        eur_instrument_id: make_instrument(
            eur_instrument_id,
            symbol="EURSTK",
            currency="EUR",
        ),
    }

    histories = {
        usd_instrument_id: (
            make_bar(date(2026, 1, 1), "100"),
            make_bar(date(2026, 1, 2), "120"),
        ),
        eur_instrument_id: (
            make_bar(date(2026, 1, 1), "50"),
            make_bar(date(2026, 1, 2), "60"),
        ),
    }

    service = make_service(
        (usd_position, eur_position),
        instruments,
        histories,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    assert result.quality == "sufficient"
    assert [item.currency for item in result.currencies] == [
        "EUR",
        "USD",
    ]

    eur = result.currencies[0]
    usd = result.currencies[1]

    assert eur.initial_value == Decimal("50")
    assert eur.latest_value == Decimal("60")
    assert eur.period_return == Decimal("0.2")

    assert usd.initial_value == Decimal("100")
    assert usd.latest_value == Decimal("120")
    assert usd.period_return == Decimal("0.2")


@pytest.mark.asyncio
async def test_marks_single_observation_as_insufficient() -> None:
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="TEST",
        currency="USD",
    )
    position = make_position_record(instrument_id)

    service = make_service(
        (position,),
        {instrument_id: instrument},
        {
            instrument_id: (make_bar(date(2026, 1, 1), "100"),),
        },
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    currency = result.currencies[0]

    assert result.quality == "insufficient"
    assert currency.quality == "insufficient"
    assert currency.observation_count == 1
    assert currency.return_count == 0
    assert currency.initial_value == Decimal("100")
    assert currency.latest_value == Decimal("100")
    assert currency.period_return is None


@pytest.mark.asyncio
async def test_marks_missing_common_history_as_unavailable() -> None:
    first_instrument_id = uuid4()
    second_instrument_id = uuid4()

    first_position = make_position_record(first_instrument_id)
    second_position = make_position_record(second_instrument_id)

    instruments = {
        first_instrument_id: make_instrument(
            first_instrument_id,
            symbol="FIRST",
            currency="USD",
        ),
        second_instrument_id: make_instrument(
            second_instrument_id,
            symbol="SECOND",
            currency="USD",
        ),
    }

    histories = {
        first_instrument_id: (
            make_bar(date(2026, 1, 1), "100"),
            make_bar(date(2026, 1, 2), "110"),
        ),
        second_instrument_id: (
            make_bar(date(2026, 1, 3), "200"),
            make_bar(date(2026, 1, 4), "220"),
        ),
    }

    service = make_service(
        (first_position, second_position),
        instruments,
        histories,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    currency = result.currencies[0]

    assert result.quality == "unavailable"
    assert currency.quality == "unavailable"
    assert currency.observation_count == 0
    assert currency.return_count == 0
    assert currency.initial_value is None
    assert currency.latest_value is None
    assert currency.period_return is None
    assert currency.first_observed_on is None
    assert currency.last_observed_on is None


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_quality() -> None:
    service = make_service(
        (),
        {},
        {},
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    assert result.position_count == 0
    assert result.quality == "empty"
    assert result.currencies == ()


@pytest.mark.asyncio
async def test_rejects_non_positive_lookback() -> None:
    service = make_service(
        (),
        {},
        {},
    )

    with pytest.raises(
        ValueError,
        match="lookback_days must be greater than zero",
    ):
        await service.build(
            USER_ID,
            PORTFOLIO_ID,
            assessed_at=ASSESSED_AT,
            lookback_days=0,
        )
