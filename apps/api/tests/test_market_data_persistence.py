from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.market_data.models import Bar, Instrument, Quote
from app.market_data.persistence import MarketDataPersistenceService


@pytest.mark.asyncio
async def test_upsert_instrument_is_idempotent(db_session) -> None:
    service = MarketDataPersistenceService(db_session)

    instrument_id = uuid4()

    first = Instrument(
        id=instrument_id,
        symbol=f"TST{instrument_id.hex[:6].upper()}",
        name="Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    persisted_first = await service.upsert_instrument(first)
    await service.commit()

    second = first.model_copy(
        update={
            "name": "Updated Test Instrument",
            "is_active": False,
        },
    )

    persisted_second = await service.upsert_instrument(second)
    await service.commit()

    assert persisted_second.id == persisted_first.id
    assert persisted_second.name == "Updated Test Instrument"
    assert persisted_second.is_active is False


@pytest.mark.asyncio
async def test_upsert_bar_deduplicates_same_instrument_timestamp_and_source(
    db_session,
) -> None:
    service = MarketDataPersistenceService(db_session)

    instrument = Instrument(
        id=uuid4(),
        symbol=f"BAR{uuid4().hex[:6].upper()}",
        name="Bar Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
    )

    persisted = await service.upsert_instrument(instrument)

    timestamp = datetime(2026, 1, 2, 12, tzinfo=UTC)

    first_bar = Bar(
        instrument_id=persisted.id,
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("103"),
        volume=Decimal("1000"),
        source="test-provider",
    )

    second_bar = first_bar.model_copy(
        update={
            "close": Decimal("107"),
            "volume": Decimal("1500"),
        },
    )

    await service.upsert_bars([first_bar])
    await service.commit()

    await service.upsert_bars([second_bar])
    await service.commit()

    count = await db_session.scalar(
        select(func.count(MarketBar.id)).where(
            MarketBar.instrument_id == persisted.id,
            MarketBar.timestamp == timestamp,
            MarketBar.source == "test-provider",
        ),
    )

    assert count == 1

    stored = await db_session.scalar(
        select(MarketBar).where(
            MarketBar.instrument_id == persisted.id,
            MarketBar.timestamp == timestamp,
            MarketBar.source == "test-provider",
        ),
    )

    assert stored is not None
    assert stored.close == Decimal("107")
    assert stored.volume == Decimal("1500")


@pytest.mark.asyncio
async def test_upsert_quote_deduplicates_same_instrument_timestamp_and_source(
    db_session,
) -> None:
    service = MarketDataPersistenceService(db_session)

    instrument = Instrument(
        id=uuid4(),
        symbol=f"QTE{uuid4().hex[:6].upper()}",
        name="Quote Test Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
    )

    persisted = await service.upsert_instrument(instrument)

    timestamp = datetime(2026, 1, 3, 12, tzinfo=UTC)

    first_quote = Quote(
        instrument_id=persisted.id,
        timestamp=timestamp,
        price=Decimal("200"),
        bid=Decimal("199.50"),
        ask=Decimal("200.50"),
        volume=Decimal("500"),
        source="test-provider",
    )

    second_quote = first_quote.model_copy(
        update={
            "price": Decimal("205"),
            "bid": Decimal("204.50"),
            "ask": Decimal("205.50"),
            "volume": Decimal("750"),
        },
    )

    await service.upsert_quote(first_quote)
    await service.commit()

    await service.upsert_quote(second_quote)
    await service.commit()

    count = await db_session.scalar(
        select(func.count(MarketQuote.id)).where(
            MarketQuote.instrument_id == persisted.id,
            MarketQuote.timestamp == timestamp,
            MarketQuote.source == "test-provider",
        ),
    )

    assert count == 1

    stored = await db_session.scalar(
        select(MarketQuote).where(
            MarketQuote.instrument_id == persisted.id,
            MarketQuote.timestamp == timestamp,
            MarketQuote.source == "test-provider",
        ),
    )

    assert stored is not None
    assert stored.price == Decimal("205")
    assert stored.bid == Decimal("204.50")
    assert stored.ask == Decimal("205.50")
    assert stored.volume == Decimal("750")
