from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.market_data.models import (
    Bar,
    Fundamentals,
    Instrument,
    MarketDataProviderHealth,
    Quote,
)


class MarketDataProvider(Protocol):
    """Interface implemented by external market-data providers."""

    name: str

    async def health_check(self) -> MarketDataProviderHealth:
        """Check whether the provider can currently serve requests."""

    async def get_instrument(
        self,
        symbol: str,
    ) -> Instrument | None:
        """Return a normalized instrument by symbol."""

    async def get_quote(
        self,
        instrument_id: UUID,
    ) -> Quote | None:
        """Return the latest quote for an instrument."""

    async def get_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        """Return normalized OHLCV bars for an instrument and time range."""

    async def get_fundamentals(
        self,
        instrument_id: UUID,
    ) -> Fundamentals | None:
        """Return the latest normalized fundamentals snapshot for an instrument."""
