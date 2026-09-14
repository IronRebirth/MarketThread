from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models.instrument import Instrument
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.market_data.repository import MarketDataRepository


async def create_instrument(
    db_session,
    *,
    symbol: str,
    exchange: str = "TEST",
) -> Instrument:
    instrument = Instrument(
        symbol=symbol,
        name="Repository Test Instrument",
        exchange=exchange,
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    return instrument


@pytest.mark.asyncio
async def test_get_instrument_returns_persisted_instrument(
    db_session,
) -> None:
    symbol = f"REP{uuid4().hex[:8].upper()}"

    instrument = await create_instrument(
        db_session,
        symbol=symbol,
    )

    repository = MarketDataRepository(db_session)

    result = await repository.get_instrument(symbol)

    assert result is not None
    assert result.id == instrument.id
    assert result.symbol == symbol


@pytest.mark.asyncio
async def test_get_instrument_returns_none_for_ambiguous_symbol(
    db_session,
) -> None:
    symbol = f"AMB{uuid4().hex[:8].upper()}"

    first = await create_instrument(
        db_session,
        symbol=symbol,
        exchange="NYSE",
    )
    second = await create_instrument(
        db_session,
        symbol=symbol,
        exchange="NASDAQ",
    )

    assert first.id != second.id

    repository = MarketDataRepository(db_session)

    result = await repository.get_instrument(symbol)

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_quote_returns_most_recent_quote(
    db_session,
) -> None:
    instrument = await create_instrument(
        db_session,
        symbol=f"QTR{uuid4().hex[:8].upper()}",
    )

    base_time = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=UTC,
    )

    db_session.add_all(
        [
            MarketQuote(
                instrument_id=instrument.id,
                timestamp=base_time,
                price=Decimal("100"),
                bid=Decimal("99"),
                ask=Decimal("101"),
                volume=Decimal("1000"),
                source="test",
            ),
            MarketQuote(
                instrument_id=instrument.id,
                timestamp=base_time + timedelta(minutes=1),
                price=Decimal("105"),
                bid=Decimal("104"),
                ask=Decimal("106"),
                volume=Decimal("1200"),
                source="test",
            ),
        ],
    )
    await db_session.commit()

    repository = MarketDataRepository(db_session)

    result = await repository.get_latest_quote(instrument.id)

    assert result is not None
    assert result.price == Decimal("105")
    assert result.timestamp == base_time + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_get_historical_bars_returns_ordered_range(
    db_session,
) -> None:
    instrument = await create_instrument(
        db_session,
        symbol=f"BAR{uuid4().hex[:8].upper()}",
    )

    first_timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=UTC,
    )

    second_timestamp = first_timestamp + timedelta(days=1)
    outside_timestamp = second_timestamp + timedelta(days=1)

    db_session.add_all(
        [
            MarketBar(
                instrument_id=instrument.id,
                timestamp=second_timestamp,
                open=Decimal("110"),
                high=Decimal("112"),
                low=Decimal("109"),
                close=Decimal("111"),
                volume=Decimal("1500"),
                source="test",
            ),
            MarketBar(
                instrument_id=instrument.id,
                timestamp=first_timestamp,
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("99"),
                close=Decimal("101"),
                volume=Decimal("1200"),
                source="test",
            ),
            MarketBar(
                instrument_id=instrument.id,
                timestamp=outside_timestamp,
                open=Decimal("120"),
                high=Decimal("122"),
                low=Decimal("119"),
                close=Decimal("121"),
                volume=Decimal("1600"),
                source="test",
            ),
        ],
    )
    await db_session.commit()

    repository = MarketDataRepository(db_session)

    result = await repository.get_historical_bars(
        instrument.id,
        first_timestamp,
        outside_timestamp,
    )

    assert len(result) == 2
    assert result[0].timestamp == first_timestamp
    assert result[1].timestamp == second_timestamp


@pytest.mark.asyncio
async def test_get_instrument_by_id_returns_persisted_record(
    db_session,
) -> None:
    instrument = await create_instrument(
        db_session,
        symbol=f"ID{uuid4().hex[:8].upper()}",
    )

    repository = MarketDataRepository(db_session)

    result = await repository.get_instrument_by_id(instrument.id)

    assert result is not None
    assert result.id == instrument.id


@pytest.mark.asyncio
async def test_get_historical_bars_for_instruments_groups_and_orders_rows(
    db_session,
) -> None:
    first_instrument = await create_instrument(
        db_session,
        symbol=f"GRP{uuid4().hex[:8].upper()}",
    )
    second_instrument = await create_instrument(
        db_session,
        symbol=f"GRP{uuid4().hex[:8].upper()}",
    )

    first_timestamp = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=UTC,
    )
    second_timestamp = first_timestamp + timedelta(days=1)

    db_session.add_all(
        [
            MarketBar(
                instrument_id=second_instrument.id,
                timestamp=first_timestamp,
                open=Decimal("200"),
                high=Decimal("202"),
                low=Decimal("199"),
                close=Decimal("201"),
                volume=Decimal("1500"),
                source="test",
            ),
            MarketBar(
                instrument_id=first_instrument.id,
                timestamp=second_timestamp,
                open=Decimal("110"),
                high=Decimal("112"),
                low=Decimal("109"),
                close=Decimal("111"),
                volume=Decimal("1400"),
                source="test",
            ),
            MarketBar(
                instrument_id=first_instrument.id,
                timestamp=first_timestamp,
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("99"),
                close=Decimal("101"),
                volume=Decimal("1200"),
                source="test",
            ),
        ],
    )
    await db_session.commit()

    repository = MarketDataRepository(db_session)

    result = await repository.get_historical_bars_for_instruments(
        instrument_ids=(
            first_instrument.id,
            second_instrument.id,
        ),
        start_after=first_timestamp - timedelta(minutes=1),
        end_at=second_timestamp,
    )

    assert set(result) == {
        first_instrument.id,
        second_instrument.id,
    }

    assert [bar.timestamp for bar in result[first_instrument.id]] == [
        first_timestamp,
        second_timestamp,
    ]

    assert result[second_instrument.id][0].timestamp == first_timestamp
