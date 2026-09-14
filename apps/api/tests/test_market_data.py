from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.market_data.models import Bar, Instrument, Quote
from app.market_data.repository import MarketDataRepository
from app.market_data.service import MarketDataService


class FakeMarketDataProvider:
    """Deterministic provider used to test the market-data service."""

    name = "test-provider"

    def __init__(self) -> None:
        self.instrument = Instrument(
            id=uuid4(),
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_class="equity",
            currency="USD",
        )
        self.quote = Quote(
            instrument_id=self.instrument.id,
            timestamp=datetime.now(UTC),
            price=Decimal("200.12"),
            bid=Decimal("200.10"),
            ask=Decimal("200.14"),
            volume=Decimal("1000"),
            source=self.name,
        )

    async def get_instrument(
        self,
        symbol: str,
    ) -> Instrument | None:
        if symbol == self.instrument.symbol:
            return self.instrument

        return None

    async def get_quote(
        self,
        instrument_id: UUID,
    ) -> Quote | None:
        if instrument_id == self.instrument.id:
            return self.quote

        return None

    async def get_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        if instrument_id != self.instrument.id:
            return []

        return [
            Bar(
                instrument_id=instrument_id,
                timestamp=start,
                open=Decimal("198.00"),
                high=Decimal("201.00"),
                low=Decimal("197.50"),
                close=Decimal("200.00"),
                volume=Decimal("5000"),
                source=self.name,
            ),
        ]


@pytest.mark.asyncio
async def test_get_instrument_normalizes_symbol() -> None:
    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    instrument = await service.get_instrument("  aapl  ")

    assert instrument is not None
    assert instrument.symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_instrument_returns_none_for_blank_symbol() -> None:
    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    instrument = await service.get_instrument("   ")

    assert instrument is None


@pytest.mark.asyncio
async def test_get_latest_quote() -> None:
    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    quote = await service.get_latest_quote(provider.instrument.id)

    assert quote is not None
    assert quote.price == Decimal("200.12")
    assert quote.source == "test-provider"


@pytest.mark.asyncio
async def test_get_historical_bars() -> None:
    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)

    bars = await service.get_historical_bars(
        provider.instrument.id,
        start,
        end,
    )

    assert len(bars) == 1
    assert bars[0].close == Decimal("200.00")


@pytest.mark.asyncio
async def test_get_historical_bars_rejects_invalid_range() -> None:
    provider = FakeMarketDataProvider()
    service = MarketDataService(provider)

    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="start must be earlier than end"):
        await service.get_historical_bars(
            provider.instrument.id,
            timestamp,
            timestamp,
        )


@pytest.mark.asyncio
async def test_database_is_authoritative_before_provider(
    db_session,
) -> None:
    provider = FakeMarketDataProvider()

    symbol = f"DB{uuid4().hex[:8].upper()}"

    instrument = InstrumentRecord(
        symbol=symbol,
        name="Persisted Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    repository = MarketDataRepository(db_session)
    service = MarketDataService(
        provider=provider,
        repository=repository,
    )

    result = await service.get_instrument(symbol.lower())

    assert result is not None
    assert result.id == instrument.id
    assert result.name == "Persisted Instrument"


@pytest.mark.asyncio
async def test_database_quote_is_used_before_provider(
    db_session,
) -> None:
    provider = FakeMarketDataProvider()

    instrument = InstrumentRecord(
        symbol=f"QDB{uuid4().hex[:8].upper()}",
        name="Persisted Quote Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        tzinfo=UTC,
    )

    db_session.add(
        MarketQuote(
            instrument_id=instrument.id,
            timestamp=timestamp,
            price=Decimal("321.45"),
            bid=Decimal("321.40"),
            ask=Decimal("321.50"),
            volume=Decimal("2500"),
            source="persisted-test",
        ),
    )
    await db_session.commit()

    repository = MarketDataRepository(db_session)
    service = MarketDataService(
        provider=provider,
        repository=repository,
    )

    result = await service.get_latest_quote(instrument.id)

    assert result is not None
    assert result.price == Decimal("321.45")
    assert result.source == "persisted-test"


@pytest.mark.asyncio
async def test_database_bars_are_used_before_provider(
    db_session,
) -> None:
    provider = FakeMarketDataProvider()

    instrument = InstrumentRecord(
        symbol=f"BDB{uuid4().hex[:8].upper()}",
        name="Persisted Bar Instrument",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    start = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )
    end = datetime(
        2026,
        1,
        3,
        tzinfo=UTC,
    )

    db_session.add(
        MarketBar(
            instrument_id=instrument.id,
            timestamp=datetime(
                2026,
                1,
                2,
                tzinfo=UTC,
            ),
            open=Decimal("300"),
            high=Decimal("310"),
            low=Decimal("295"),
            close=Decimal("307"),
            volume=Decimal("5000"),
            source="persisted-test",
        ),
    )
    await db_session.commit()

    repository = MarketDataRepository(db_session)
    service = MarketDataService(
        provider=provider,
        repository=repository,
    )

    result = await service.get_historical_bars(
        instrument.id,
        start,
        end,
    )

    assert len(result) == 1
    assert result[0].close == Decimal("307")
    assert result[0].source == "persisted-test"
