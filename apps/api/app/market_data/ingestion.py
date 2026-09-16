from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.market_data.models import Bar, MarketDataIngestionResult, Quote
from app.market_data.persistence import MarketDataPersistenceService
from app.market_data.providers.base import MarketDataProvider
from app.market_data.validation import validate_bars, validate_quote


class MarketDataIngestionService:
    """Coordinate provider retrieval and transactional market-data persistence."""

    def __init__(
        self,
        provider: MarketDataProvider,
        persistence: MarketDataPersistenceService,
    ) -> None:
        self.provider = provider
        self.persistence = persistence

    async def ingest(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        include_quote: bool = True,
    ) -> MarketDataIngestionResult | None:
        """Fetch, validate, and persist market data for an instrument."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be blank")

        if start >= end:
            raise ValueError("start must be earlier than end")

        instrument = await self.provider.get_instrument(normalized_symbol)

        if instrument is None:
            return None

        try:
            quote = None
            if include_quote:
                quote = await self.provider.get_quote(instrument.id)

            bars = await self.provider.get_bars(
                instrument.id,
                start,
                end,
            )

            validated_quote = validate_quote(quote) if quote is not None else None
            validated_bars = validate_bars(list(bars))

            persisted_instrument = await self.persistence.upsert_instrument(
                instrument,
            )

            normalized_quote = self._remap_quote(
                validated_quote,
                persisted_instrument.id,
            )
            normalized_bars = self._remap_bars(
                validated_bars,
                persisted_instrument.id,
            )

            quote_persisted = False

            if normalized_quote is not None:
                await self.persistence.upsert_quote(normalized_quote)
                quote_persisted = True

            bars_persisted = await self.persistence.upsert_bars(
                normalized_bars,
            )

            await self.persistence.commit()

            return MarketDataIngestionResult(
                instrument_id=persisted_instrument.id,
                symbol=persisted_instrument.symbol,
                exchange=persisted_instrument.exchange,
                bars_received=len(bars),
                bars_persisted=bars_persisted,
                quote_received=quote is not None,
                quote_persisted=quote_persisted,
            )
        except Exception:
            await self.persistence.rollback()
            raise

    @staticmethod
    def _remap_quote(
        quote: Quote | None,
        instrument_id: UUID,
    ) -> Quote | None:
        """Map provider instrument IDs to the persisted instrument ID."""

        if quote is None:
            return None

        return quote.model_copy(
            update={"instrument_id": instrument_id},
        )

    @staticmethod
    def _remap_bars(
        bars: Sequence[Bar],
        instrument_id: UUID,
    ) -> list[Bar]:
        """Map provider instrument IDs to the persisted instrument ID."""

        return [
            bar.model_copy(
                update={"instrument_id": instrument_id},
            )
            for bar in bars
        ]
