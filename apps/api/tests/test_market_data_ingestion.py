from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import Bar, Instrument, Quote
from app.market_data.persistence import MarketDataPersistenceService


class FakeIngestionProvider:
    """Deterministic provider used to test market-data ingestion."""

    name = "test-provider"

    def __init__(
        self,
        symbol: str = "AAPL",
    ) -> None:
        self.provider_instrument_id = uuid4()
        self.instrument = Instrument(
            id=self.provider_instrument_id,
            symbol=symbol,
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_class="equity",
            currency="USD",
        )

        timestamp = datetime(2026, 1, 2, 12, tzinfo=UTC)

        self.quote = Quote(
            instrument_id=self.provider_instrument_id,
            timestamp=timestamp,
            price=Decimal("200"),
            bid=Decimal("199.50"),
            ask=Decimal("200.50"),
            volume=Decimal("1000"),
            source=self.name,
        )

        self.bars = [
            Bar(
                instrument_id=self.provider_instrument_id,
                timestamp=timestamp,
                open=Decimal("198"),
                high=Decimal("202"),
                low=Decimal("197"),
                close=Decimal("200"),
                volume=Decimal("5000"),
                source=self.name,
            ),
        ]

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
        if instrument_id == self.provider_instrument_id:
            return self.quote

        return None

    async def get_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        if instrument_id != self.provider_instrument_id:
            return []

        return self.bars


@pytest.mark.asyncio
async def test_ingestion_persists_instrument_quote_and_bars(db_session) -> None:
    provider = FakeIngestionProvider()
    persistence = MarketDataPersistenceService(db_session)
    service = MarketDataIngestionService(provider, persistence)

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 4, tzinfo=UTC)

    result = await service.ingest(
        symbol=" aapl ",
        start=start,
        end=end,
    )

    assert result is not None
    assert result.symbol == "AAPL"
    assert result.exchange == "NASDAQ"
    assert result.bars_received == 1
    assert result.bars_persisted == 1
    assert result.quote_received is True
    assert result.quote_persisted is True

    instrument = await db_session.scalar(
        select(InstrumentRecord).where(
            InstrumentRecord.id == result.instrument_id,
        ),
    )
    assert instrument is not None
    assert instrument.symbol == "AAPL"

    quote = await db_session.scalar(
        select(MarketQuote).where(
            MarketQuote.instrument_id == result.instrument_id,
        ),
    )
    assert quote is not None
    assert quote.price == Decimal("200")

    bar = await db_session.scalar(
        select(MarketBar).where(
            MarketBar.instrument_id == result.instrument_id,
        ),
    )
    assert bar is not None
    assert bar.close == Decimal("200")


@pytest.mark.asyncio
async def test_ingestion_reuses_existing_internal_instrument_id(
    db_session,
) -> None:
    symbol = f"REUSE{uuid4().hex[:8].upper()}"
    provider = FakeIngestionProvider(symbol=symbol)
    persistence = MarketDataPersistenceService(db_session)
    service = MarketDataIngestionService(provider, persistence)

    existing_id = uuid4()

    existing = InstrumentRecord(
        id=existing_id,
        symbol=symbol,
        name="Existing Test Instrument",
        exchange="NASDAQ",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )

    db_session.add(existing)
    await db_session.commit()

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 4, tzinfo=UTC)

    result = await service.ingest(
        symbol=symbol,
        start=start,
        end=end,
    )

    assert result is not None
    assert result.instrument_id == existing_id

    quote = await db_session.scalar(
        select(MarketQuote).where(
            MarketQuote.instrument_id == existing_id,
        ),
    )
    assert quote is not None

    bar = await db_session.scalar(
        select(MarketBar).where(
            MarketBar.instrument_id == existing_id,
        ),
    )
    assert bar is not None


@pytest.mark.asyncio
async def test_ingestion_returns_none_for_unknown_instrument(db_session) -> None:
    provider = FakeIngestionProvider()
    persistence = MarketDataPersistenceService(db_session)
    service = MarketDataIngestionService(provider, persistence)

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 4, tzinfo=UTC)

    result = await service.ingest(
        symbol="MSFT",
        start=start,
        end=end,
    )

    assert result is None


@pytest.mark.asyncio
async def test_ingestion_rejects_invalid_date_range(db_session) -> None:
    provider = FakeIngestionProvider()
    persistence = MarketDataPersistenceService(db_session)
    service = MarketDataIngestionService(provider, persistence)

    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="start must be earlier than end",
    ):
        await service.ingest(
            symbol="AAPL",
            start=timestamp,
            end=timestamp,
        )
