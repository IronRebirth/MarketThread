from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.market_data.models import Bar, Instrument, Quote
from app.market_data.providers.base import MarketDataProvider


class MarketDataService:
    """Coordinate normalized market-data retrieval."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    async def get_instrument(
        self,
        symbol: str,
    ) -> Instrument | None:
        """Retrieve a normalized instrument."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            return None

        return await self.provider.get_instrument(normalized_symbol)

    async def get_latest_quote(
        self,
        instrument_id: UUID,
    ) -> Quote | None:
        """Retrieve the latest quote."""

        return await self.provider.get_quote(instrument_id)

    async def get_historical_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        """Retrieve historical OHLCV bars."""

        if start >= end:
            raise ValueError("start must be earlier than end")

        return await self.provider.get_bars(
            instrument_id,
            start,
            end,
        )
