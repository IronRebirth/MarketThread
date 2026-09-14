from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.instrument import Instrument as InstrumentRecord
from app.db.models.market_bar import MarketBar
from app.db.models.market_data import MarketQuote


class MarketDataRepository:
    """Read persisted normalized market data from PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_instrument(
        self,
        symbol: str,
    ) -> InstrumentRecord | None:
        """Return the unique active instrument for a symbol."""

        result = await self.session.execute(
            select(InstrumentRecord)
            .where(
                InstrumentRecord.symbol == symbol,
                InstrumentRecord.is_active.is_(True),
            )
            .order_by(
                InstrumentRecord.exchange,
                InstrumentRecord.id,
            ),
        )

        instruments = result.scalars().all()

        if len(instruments) != 1:
            return None

        return instruments[0]

    async def get_instrument_by_id(
        self,
        instrument_id: UUID,
    ) -> InstrumentRecord | None:
        """Return an instrument by its internal identifier."""

        return await self.session.get(
            InstrumentRecord,
            instrument_id,
        )

    async def get_latest_quote(
        self,
        instrument_id: UUID,
    ) -> MarketQuote | None:
        """Return the latest persisted quote for an instrument."""

        result = await self.session.execute(
            select(MarketQuote)
            .where(
                MarketQuote.instrument_id == instrument_id,
            )
            .order_by(
                MarketQuote.timestamp.desc(),
                MarketQuote.id.desc(),
            )
            .limit(1),
        )

        return result.scalar_one_or_none()

    async def get_historical_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[MarketBar]:
        """Return persisted OHLCV bars within the requested time range."""

        result = await self.session.execute(
            select(MarketBar)
            .where(
                MarketBar.instrument_id == instrument_id,
                MarketBar.timestamp >= start,
                MarketBar.timestamp < end,
            )
            .order_by(
                MarketBar.timestamp,
                MarketBar.id,
            ),
        )

        return tuple(result.scalars().all())

    async def get_historical_bars_for_instruments(
        self,
        instrument_ids: Sequence[UUID],
        start_after: datetime,
        end_at: datetime,
    ) -> dict[UUID, list[MarketBar]]:
        """Return ordered persisted bars grouped by instrument."""

        if not instrument_ids:
            return {}

        result = await self.session.execute(
            select(MarketBar)
            .where(
                MarketBar.instrument_id.in_(instrument_ids),
                MarketBar.timestamp > start_after,
                MarketBar.timestamp <= end_at,
            )
            .order_by(
                MarketBar.instrument_id,
                MarketBar.timestamp,
                MarketBar.id,
            ),
        )

        grouped: dict[UUID, list[MarketBar]] = defaultdict(list)

        for bar in result.scalars().all():
            grouped[bar.instrument_id].append(bar)

        return grouped
