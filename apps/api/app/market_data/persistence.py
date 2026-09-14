from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.market_bar import MarketBar as MarketBarRecord
from app.db.models.market_data import MarketQuote as MarketQuoteRecord
from app.market_data.models import Bar, Instrument, Quote


class MarketDataPersistenceService:
    """Persist normalized market data with idempotent upsert semantics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_instrument(
        self,
        instrument: Instrument,
    ) -> InstrumentRecord:
        """Create or update an instrument atomically."""

        statement = insert(InstrumentRecord).values(
            id=instrument.id,
            symbol=instrument.symbol,
            name=instrument.name,
            exchange=instrument.exchange,
            asset_class=instrument.asset_class,
            currency=instrument.currency,
            is_active=instrument.is_active,
        )

        statement = statement.on_conflict_do_update(
            constraint="uq_instruments_symbol_exchange",
            set_={
                "name": statement.excluded.name,
                "asset_class": statement.excluded.asset_class,
                "currency": statement.excluded.currency,
                "is_active": statement.excluded.is_active,
            },
        ).returning(InstrumentRecord.id)

        result = await self.session.execute(statement)
        instrument_id = result.scalar_one()

        persisted = await self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.id == instrument_id,
            ),
        )

        if persisted is None:
            raise RuntimeError(
                "Instrument upsert succeeded but the persisted instrument "
                "could not be loaded.",
            )

        await self.session.refresh(persisted)

        return persisted

    async def upsert_quote(
        self,
        quote: Quote,
    ) -> MarketQuoteRecord:
        """Create or update a quote using instrument, timestamp, and source."""

        statement = insert(MarketQuoteRecord).values(
            instrument_id=quote.instrument_id,
            timestamp=quote.timestamp,
            price=quote.price,
            bid=quote.bid,
            ask=quote.ask,
            volume=quote.volume,
            source=quote.source,
        )

        statement = statement.on_conflict_do_update(
            constraint="uq_market_quotes_instrument_timestamp_source",
            set_={
                "price": statement.excluded.price,
                "bid": statement.excluded.bid,
                "ask": statement.excluded.ask,
                "volume": statement.excluded.volume,
            },
        ).returning(MarketQuoteRecord.id)

        result = await self.session.execute(statement)
        quote_id = result.scalar_one()

        persisted = await self.session.scalar(
            select(MarketQuoteRecord).where(
                MarketQuoteRecord.id == quote_id,
            ),
        )

        if persisted is None:
            raise RuntimeError(
                "Quote upsert succeeded but the persisted quote could not be loaded.",
            )

        await self.session.refresh(persisted)

        return persisted

    async def upsert_bars(
        self,
        bars: Sequence[Bar],
    ) -> int:
        """Create or update bars using instrument, timestamp, and source."""

        if not bars:
            return 0

        values = [
            {
                "instrument_id": bar.instrument_id,
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "source": bar.source,
            }
            for bar in bars
        ]

        statement = insert(MarketBarRecord).values(values)

        statement = statement.on_conflict_do_update(
            constraint="uq_market_bars_instrument_timestamp_source",
            set_={
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
            },
        )

        await self.session.execute(statement)

        return len(values)

    async def commit(self) -> None:
        """Commit the current persistence transaction."""

        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current persistence transaction."""

        await self.session.rollback()
