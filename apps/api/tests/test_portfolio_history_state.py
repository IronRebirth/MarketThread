from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.portfolio.history import PortfolioHistoricalStateService

PORTFOLIO_ID = uuid4()
USER_ID = uuid4()


def make_instrument(
    instrument_id: UUID,
    *,
    symbol: str = "TEST",
    currency: str = "USD",
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
    event_type: str,
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
        histories: tuple[SimpleNamespace, ...],
        instruments: dict[UUID, SimpleNamespace],
    ) -> None:
        self.histories = histories
        self.session = FakeSession(instruments)

    async def get_for_user(
        self,
        _user_id: UUID,
        _portfolio_id: UUID,
    ) -> tuple[SimpleNamespace, int]:
        return (
            SimpleNamespace(
                id=PORTFOLIO_ID,
                name="Historical Portfolio",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 10, tzinfo=UTC),
            ),
            1,
        )

    async def list_position_history_at(
        self,
        _user_id: UUID,
        _portfolio_id: UUID,
        as_of: datetime,
    ) -> tuple[SimpleNamespace, ...]:
        latest_by_instrument: dict[UUID, SimpleNamespace] = {}

        for history in self.histories:
            if history.recorded_at > as_of:
                continue

            current = latest_by_instrument.get(history.instrument_id)

            if current is None or (
                history.recorded_at,
                history.sequence_id,
            ) > (
                current.recorded_at,
                current.sequence_id,
            ):
                latest_by_instrument[history.instrument_id] = history

        return tuple(
            sorted(
                latest_by_instrument.values(),
                key=lambda history: (
                    history.instrument_id,
                    history.sequence_id,
                ),
            ),
        )


def make_service(
    histories: tuple[SimpleNamespace, ...],
    instruments: dict[UUID, SimpleNamespace],
) -> PortfolioHistoricalStateService:
    return PortfolioHistoricalStateService(
        FakePersistence(
            histories,
            instruments,
        ),
    )


@pytest.mark.asyncio
async def test_reconstructs_active_positions_from_history() -> None:
    instrument_id = uuid4()

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="10",
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
        make_history(
            2,
            instrument_id,
            quantity="25",
            average_cost="110",
            event_type="updated",
            recorded_at=datetime(
                2026,
                1,
                5,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories,
        {instrument_id: make_instrument(instrument_id)},
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        as_of=datetime(
            2026,
            1,
            6,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert result.quality == "complete"
    assert result.position_count == 1
    assert result.portfolio.position_count == 1

    position = result.positions[0]

    assert position.history_sequence_id == 2
    assert position.instrument_id == instrument_id
    assert position.quantity == Decimal("25")
    assert position.average_cost == Decimal("110")
    assert position.event_type == "updated"
    assert position.symbol == "TEST"
    assert position.currency == "USD"


@pytest.mark.asyncio
async def test_reconstructs_state_before_a_later_update() -> None:
    instrument_id = uuid4()

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="10",
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
        make_history(
            2,
            instrument_id,
            quantity="25",
            average_cost="110",
            event_type="updated",
            recorded_at=datetime(
                2026,
                1,
                5,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories,
        {instrument_id: make_instrument(instrument_id)},
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        as_of=datetime(
            2026,
            1,
            4,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert result.quality == "complete"
    assert result.position_count == 1

    position = result.positions[0]

    assert position.history_sequence_id == 1
    assert position.quantity == Decimal("10")
    assert position.average_cost == Decimal("100")
    assert position.event_type == "created"


@pytest.mark.asyncio
async def test_zero_quantity_delete_state_is_excluded() -> None:
    instrument_id = uuid4()

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="5",
            average_cost="80",
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
        make_history(
            2,
            instrument_id,
            quantity="0",
            average_cost="80",
            event_type="deleted",
            recorded_at=datetime(
                2026,
                1,
                4,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories,
        {instrument_id: make_instrument(instrument_id)},
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        as_of=datetime(
            2026,
            1,
            5,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert result.quality == "empty"
    assert result.position_count == 0
    assert result.portfolio.position_count == 0
    assert result.positions == ()


@pytest.mark.asyncio
async def test_reconstructs_only_events_known_at_as_of_time() -> None:
    instrument_id = uuid4()

    histories = (
        make_history(
            1,
            instrument_id,
            quantity="10",
            average_cost="100",
            event_type="created",
            recorded_at=datetime(
                2026,
                1,
                5,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
    )

    service = make_service(
        histories,
        {instrument_id: make_instrument(instrument_id)},
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        as_of=datetime(
            2026,
            1,
            4,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert result.quality == "empty"
    assert result.position_count == 0
    assert result.positions == ()


@pytest.mark.asyncio
async def test_reconstructed_state_preserves_multiple_instruments() -> None:
    first_instrument_id = uuid4()
    second_instrument_id = uuid4()

    histories = (
        make_history(
            1,
            first_instrument_id,
            quantity="10",
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
        make_history(
            2,
            second_instrument_id,
            quantity="20",
            average_cost="50",
            event_type="backfilled",
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
        histories,
        {
            first_instrument_id: make_instrument(
                first_instrument_id,
                symbol="FIRST",
            ),
            second_instrument_id: make_instrument(
                second_instrument_id,
                symbol="SECOND",
            ),
        },
    )

    result = await service.build(
        USER_ID,
        PORTFOLIO_ID,
        as_of=datetime(
            2026,
            1,
            3,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert result.quality == "complete"
    assert result.position_count == 2
    assert {position.symbol for position in result.positions} == {
        "FIRST",
        "SECOND",
    }
    assert {position.quantity for position in result.positions} == {
        Decimal("10"),
        Decimal("20"),
    }


@pytest.mark.asyncio
async def test_rejects_timezone_naive_as_of() -> None:
    service = make_service(
        (),
        {},
    )

    with pytest.raises(
        ValueError,
        match="as_of must be timezone-aware",
    ):
        await service.build(
            USER_ID,
            PORTFOLIO_ID,
            as_of=datetime(
                2026,
                1,
                5,
                12,
                0,
            ),
        )


@pytest.mark.asyncio
async def test_missing_instrument_fails_reconstruction() -> None:
    instrument_id = uuid4()

    service = make_service(
        (
            make_history(
                1,
                instrument_id,
                quantity="10",
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
        ),
        {},
    )

    with pytest.raises(
        RuntimeError,
        match="Historical portfolio position references a missing instrument",
    ):
        await service.build(
            USER_ID,
            PORTFOLIO_ID,
            as_of=datetime(
                2026,
                1,
                3,
                12,
                0,
                tzinfo=UTC,
            ),
        )
