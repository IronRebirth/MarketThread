from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from app.market_data.models import (
    Bar,
    Fundamentals,
    HistoricalDataCompleteness,
    Instrument,
    MarketDataProviderHealth,
    Quote,
    QuoteFreshness,
)
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.quality import (
    assess_historical_completeness,
    assess_quote_freshness,
)
from app.market_data.repository import MarketDataRepository


class MarketDataService:
    """Coordinate database-first and provider-backed market-data retrieval."""

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        repository: MarketDataRepository | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository

    async def get_instrument(
        self,
        symbol: str,
    ) -> Instrument | None:
        """Retrieve an instrument from PostgreSQL before using the provider."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            return None

        if self.repository is not None:
            persisted = await self.repository.get_instrument(
                normalized_symbol,
            )

            if persisted is not None:
                return Instrument.model_validate(
                    {
                        "id": persisted.id,
                        "symbol": persisted.symbol,
                        "name": persisted.name,
                        "exchange": persisted.exchange,
                        "asset_class": persisted.asset_class,
                        "currency": persisted.currency,
                        "is_active": persisted.is_active,
                    },
                )

        provider = self._require_provider()

        return await provider.get_instrument(normalized_symbol)

    async def get_fundamentals(
        self,
        instrument_id: UUID,
    ) -> Fundamentals | None:
        """Retrieve persisted fundamentals before using the provider."""

        from app.market_data.repository import FundamentalRepository

        if self.repository is not None:
            persisted = await FundamentalRepository(
                self.repository.session,
            ).get_latest(instrument_id)

            if persisted is not None:
                return Fundamentals.model_validate(
                    {
                        "instrument_id": persisted.instrument_id,
                        "period_end": persisted.period_end,
                        "revenue_growth": persisted.revenue_growth,
                        "earnings_growth": persisted.earnings_growth,
                        "gross_margin": persisted.gross_margin,
                        "operating_margin": persisted.operating_margin,
                        "net_margin": persisted.net_margin,
                        "roe": persisted.roe,
                        "roic": persisted.roic,
                        "debt_to_equity": persisted.debt_to_equity,
                        "debt_to_ebitda": persisted.debt_to_ebitda,
                        "operating_cash_flow": persisted.operating_cash_flow,
                        "free_cash_flow": persisted.free_cash_flow,
                        "pe_ratio": persisted.pe_ratio,
                        "ps_ratio": persisted.ps_ratio,
                        "ev_to_ebitda": persisted.ev_to_ebitda,
                        "dividend_yield": persisted.dividend_yield,
                        "source": persisted.source,
                    },
                )

        provider = self._require_provider()
        return await provider.get_fundamentals(instrument_id)

    async def get_latest_quote(
        self,
        instrument_id: UUID,
    ) -> Quote | None:
        """Retrieve the latest quote from PostgreSQL before the provider."""

        if self.repository is not None:
            persisted = await self.repository.get_latest_quote(
                instrument_id,
            )

            if persisted is not None:
                return Quote.model_validate(
                    {
                        "instrument_id": persisted.instrument_id,
                        "timestamp": persisted.timestamp,
                        "price": persisted.price,
                        "bid": persisted.bid,
                        "ask": persisted.ask,
                        "volume": persisted.volume,
                        "source": persisted.source,
                    },
                )

        provider = self._require_provider()

        return await provider.get_quote(instrument_id)

    async def get_historical_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        """Retrieve persisted historical bars before using the provider."""

        if start >= end:
            raise ValueError("start must be earlier than end")

        if self.repository is not None:
            persisted = await self.repository.get_historical_bars(
                instrument_id,
                start,
                end,
            )

            if persisted:
                return tuple(
                    Bar.model_validate(
                        {
                            "instrument_id": bar.instrument_id,
                            "timestamp": bar.timestamp,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                            "source": bar.source,
                        },
                    )
                    for bar in persisted
                )

        provider = self._require_provider()

        return await provider.get_bars(
            instrument_id,
            start,
            end,
        )

    async def assess_quote_freshness(
        self,
        instrument_id: UUID,
        *,
        assessed_at: datetime | None = None,
        maximum_age: timedelta = timedelta(minutes=15),
    ) -> QuoteFreshness:
        """Assess freshness of the latest available quote."""

        quote = await self.get_latest_quote(instrument_id)

        return assess_quote_freshness(
            quote,
            assessed_at=assessed_at,
            maximum_age=maximum_age,
        )

    async def assess_historical_completeness(
        self,
        instrument_id: UUID,
        *,
        start: datetime,
        end: datetime,
        expected_interval: timedelta,
        minimum_coverage: float = 0.95,
    ) -> HistoricalDataCompleteness:
        """Assess coverage of the requested historical market-data range."""

        bars = await self.get_historical_bars(
            instrument_id,
            start,
            end,
        )

        return assess_historical_completeness(
            bars,
            start=start,
            end=end,
            expected_interval=expected_interval,
            minimum_coverage=minimum_coverage,
        )

    async def check_provider_health(self) -> MarketDataProviderHealth:
        """Return the health of the configured external market-data provider."""

        provider = self._require_provider()

        return await provider.health_check()

    def _require_provider(self) -> MarketDataProvider:
        """Return the provider or raise a configuration error."""

        if self.provider is None:
            raise MarketDataProviderError(
                "No persisted market data is available and no "
                "market-data provider is configured.",
            )

        return self.provider
