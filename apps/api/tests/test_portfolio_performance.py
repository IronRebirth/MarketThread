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


def make_history(
    sequence_id: int,
    instrument_id: UUID,
    *,
    quantity: str,
    average_cost: str = "100",
    event_type: str = "created",
    recorded_at: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        sequence_id=sequence_id,
        portfolio_id=PORTFOLIO_ID,
        instrument_id=instrument_id,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
        event_type=event_type,
        recorded_at=recorded_at,
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


def make_portfolio() -> SimpleNamespace:
    return SimpleNamespace(
        id=PORTFOLIO_ID,
        name="Test Portfolio",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 10, tzinfo=UTC),
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

    async def execute(
        self,
        _statement,
    ):
        return FakeExecuteResult(
            tuple(self.instruments),
        )


class FakeExecuteResult:
    def __init__(
        self,
        values: tuple[UUID, ...],
    ) -> None:
        self.values = values

    def scalars(self):
        return FakeScalarResult(self.values)


class FakeScalarResult:
    def __init__(
        self,
        values: tuple[UUID, ...],
    ) -> None:
        self.values = values

    def all(self):
        return self.values


class FakePersistence:
    def __init__(
        self,
        *,
        histories: tuple[SimpleNamespace, ...],
        instruments: dict[UUID, SimpleNamespace],
        current_position_count: int,
    ) -> None:
        self.histories = histories
        self.instruments = instruments
        self.current_position_count = current_position_count
        self.session = FakeSession(instruments)

    async def get_for_user(
        self,
        _user_id: UUID,
        _portfolio_id: UUID,
    ) -> tuple[SimpleNamespace, int]:
        return (
            make_portfolio(),
            self.current_position_count,
        )

    async def list_position_history_for_window(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[SimpleNamespace, ...]:
        latest_before_start: dict[UUID, SimpleNamespace] = {}

        for history in self.histories:
            if history.portfolio_id != portfolio_id:
                continue

            if history.recorded_at <= start_at:
                current = latest_before_start.get(
                    history.instrument_id,
                )

                if current is None or (
                    history.recorded_at,
                    history.sequence_id,
                ) > (
                    current.recorded_at,
                    current.sequence_id,
                ):
                    latest_before_start[history.instrument_id] = history

        changes = [
            history
            for history in self.histories
            if history.portfolio_id == portfolio_id
            and start_at < history.recorded_at <= end_at
        ]

        return tuple(
            sorted(
                (
                    *latest_before_start.values(),
                    *changes,
                ),
                key=lambda history: (
                    history.recorded_at,
                    history.sequence_id,
                ),
            ),
        )


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
        return self.histories.get(
            instrument_id,
            (),
        )


def make_service(
    *,
    histories: tuple[SimpleNamespace, ...],
    instruments: dict[UUID, SimpleNamespace],
    market_data: dict[UUID, tuple[SimpleNamespace, ...]],
    current_position_count: int,
) -> PortfolioPerformanceService:
    return PortfolioPerformanceService(
        FakePersistence(
            histories=histories,
            instruments=instruments,
            current_position_count=current_position_count,
        ),
        FakeMarketData(market_data),
    )


@pytest.mark.asyncio
async def test_builds_historical_values_and_period_return_for_stable_position() -> None:
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="TEST",
        currency="USD",
    )

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="2",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={instrument_id: instrument},
        market_data={
            instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
                make_bar(date(2026, 1, 3), "120"),
            ),
        },
        current_position_count=1,
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
async def test_position_added_during_window_is_reflected_in_value_series() -> None:
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="ADDED",
        currency="USD",
    )

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="0",
            average_cost="100",
            event_type="deleted",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        make_history(
            2,
            instrument_id,
            quantity="2",
            average_cost="100",
            event_type="created",
            recorded_at=datetime(
                2026,
                1,
                2,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={instrument_id: instrument},
        market_data={
            instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
                make_bar(date(2026, 1, 3), "120"),
            ),
        },
        current_position_count=1,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    currency = result.currencies[0]

    assert [point.value for point in currency.points] == [
        Decimal("0"),
        Decimal("220"),
        Decimal("240"),
    ]
    assert currency.period_return is None
    assert currency.quality == "insufficient"
    assert any(
        "first observed portfolio value is zero" in note for note in currency.notes
    )


@pytest.mark.asyncio
async def test_position_updated_during_window_changes_historical_values() -> None:
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="UPDATED",
        currency="USD",
    )

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="1",
            average_cost="100",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        make_history(
            2,
            instrument_id,
            quantity="2",
            average_cost="100",
            event_type="updated",
            recorded_at=datetime(
                2026,
                1,
                2,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={instrument_id: instrument},
        market_data={
            instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
                make_bar(date(2026, 1, 3), "120"),
            ),
        },
        current_position_count=1,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    currency = result.currencies[0]

    assert [point.value for point in currency.points] == [
        Decimal("100"),
        Decimal("220"),
        Decimal("240"),
    ]
    assert currency.period_return is None
    assert currency.quality == "insufficient"
    assert any(
        "holdings changed after the first complete observation" in note
        for note in currency.notes
    )


@pytest.mark.asyncio
async def test_position_deleted_during_window_stops_contributing_after_deletion() -> (
    None
):
    instrument_id = uuid4()

    instrument = make_instrument(
        instrument_id,
        symbol="DELETED",
        currency="USD",
    )

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="1",
            average_cost="100",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        make_history(
            2,
            instrument_id,
            quantity="0",
            average_cost="100",
            event_type="deleted",
            recorded_at=datetime(
                2026,
                1,
                2,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={instrument_id: instrument},
        market_data={
            instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
                make_bar(date(2026, 1, 3), "120"),
            ),
        },
        current_position_count=0,
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        assessed_at=ASSESSED_AT,
        lookback_days=30,
    )

    currency = result.currencies[0]

    assert [point.value for point in currency.points] == [
        Decimal("100"),
        Decimal("0"),
        Decimal("0"),
    ]
    assert currency.period_return is None
    assert currency.quality == "insufficient"
    assert any(
        "holdings changed after the first complete observation" in note
        for note in currency.notes
    )


@pytest.mark.asyncio
async def test_keeps_multiple_currencies_separate() -> None:
    usd_instrument_id = uuid4()
    eur_instrument_id = uuid4()

    usd_instrument = make_instrument(
        usd_instrument_id,
        symbol="USDSTK",
        currency="USD",
    )
    eur_instrument = make_instrument(
        eur_instrument_id,
        symbol="EURSTK",
        currency="EUR",
    )

    histories = (
        make_history(
            1,
            usd_instrument_id,
            quantity="1",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        make_history(
            2,
            eur_instrument_id,
            quantity="1",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={
            usd_instrument_id: usd_instrument,
            eur_instrument_id: eur_instrument,
        },
        market_data={
            usd_instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "120"),
            ),
            eur_instrument_id: (
                make_bar(date(2026, 1, 1), "50"),
                make_bar(date(2026, 1, 2), "60"),
            ),
        },
        current_position_count=2,
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
async def test_marks_missing_common_history_as_unavailable() -> None:
    first_instrument_id = uuid4()
    second_instrument_id = uuid4()

    first_instrument = make_instrument(
        first_instrument_id,
        symbol="FIRST",
        currency="USD",
    )
    second_instrument = make_instrument(
        second_instrument_id,
        symbol="SECOND",
        currency="USD",
    )

    histories = (
        make_history(
            1,
            first_instrument_id,
            quantity="1",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        make_history(
            2,
            second_instrument_id,
            quantity="1",
            recorded_at=datetime(
                2025,
                12,
                1,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories=histories,
        instruments={
            first_instrument_id: first_instrument,
            second_instrument_id: second_instrument,
        },
        market_data={
            first_instrument_id: (
                make_bar(date(2026, 1, 1), "100"),
                make_bar(date(2026, 1, 2), "110"),
            ),
            second_instrument_id: (
                make_bar(date(2026, 1, 3), "200"),
                make_bar(date(2026, 1, 4), "220"),
            ),
        },
        current_position_count=2,
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
        histories=(),
        instruments={},
        market_data={},
        current_position_count=0,
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
        histories=(),
        instruments={},
        market_data={},
        current_position_count=0,
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
