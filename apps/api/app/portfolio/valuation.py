from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.db.models.instrument import Instrument
from app.market_data.models import Quote, QuoteFreshness
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.quality import MarketDataQualityError, assess_quote_freshness
from app.market_data.service import MarketDataService
from app.portfolio.models import (
    Portfolio,
    PortfolioCurrencyValuation,
    PortfolioPosition,
    PortfolioPositionValuation,
    PortfolioValuation,
)
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioValuationService:
    """Build a read-only valuation from persisted positions and market quotes."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
    ) -> None:
        self.persistence = persistence
        self.market_data = market_data

    async def build(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        assessed_at: datetime | None = None,
        maximum_quote_age: timedelta = timedelta(minutes=15),
    ) -> PortfolioValuation:
        """Build a quality-aware valuation for a user-owned portfolio."""

        detail = await self.persistence.get_detail_for_user(
            user_id,
            portfolio_id,
        )

        if detail is None:
            raise ValueError("Portfolio not found.")

        portfolio_record, position_count, position_records = detail

        portfolio = Portfolio(
            portfolio_id=portfolio_record.id,
            name=portfolio_record.name,
            created_at=portfolio_record.created_at,
            updated_at=portfolio_record.updated_at,
            position_count=position_count,
        )

        assessment_time = assessed_at or datetime.now(UTC)

        valuations: list[PortfolioPositionValuation] = []

        for position_record in position_records:
            instrument = await self.persistence.session.get(
                Instrument,
                position_record.instrument_id,
            )

            if instrument is None:
                raise RuntimeError(
                    "Portfolio position references a missing instrument.",
                )

            position = PortfolioPosition(
                position_id=position_record.id,
                portfolio_id=position_record.portfolio_id,
                instrument_id=position_record.instrument_id,
                quantity=position_record.quantity,
                average_cost=position_record.average_cost,
                created_at=position_record.created_at,
                updated_at=position_record.updated_at,
                symbol=instrument.symbol,
                name=instrument.name,
                exchange=instrument.exchange,
                asset_class=instrument.asset_class,
                currency=instrument.currency,
                is_active=instrument.is_active,
            )

            valuations.append(
                await self._value_position(
                    position,
                    assessed_at=assessment_time,
                    maximum_quote_age=maximum_quote_age,
                ),
            )

        currency_valuations = self._build_currency_valuations(
            valuations,
        )

        overall_quality = self._aggregate_quality(
            valuations,
        )

        return PortfolioValuation(
            portfolio=portfolio,
            assessed_at=assessment_time,
            maximum_quote_age_seconds=maximum_quote_age.total_seconds(),
            quality=overall_quality,
            positions=tuple(valuations),
            currencies=currency_valuations,
        )

    async def _value_position(
        self,
        position: PortfolioPosition,
        *,
        assessed_at: datetime,
        maximum_quote_age: timedelta,
    ) -> PortfolioPositionValuation:
        """Value one position only when its quote is sufficiently fresh."""

        cost_basis = position.quantity * position.average_cost

        try:
            quote = await self.market_data.get_latest_quote(
                position.instrument_id,
            )
        except MarketDataProviderError:
            quote = None

        freshness = self._assess_quote(
            quote,
            assessed_at=assessed_at,
            maximum_quote_age=maximum_quote_age,
        )

        if freshness.status != "fresh" or quote is None:
            return PortfolioPositionValuation(
                position=position,
                cost_basis=cost_basis,
                quote=None,
                quote_quality=freshness,
                market_value=None,
                unrealized_pnl=None,
                unrealized_pnl_percent=None,
            )

        market_value = position.quantity * quote.price
        unrealized_pnl = market_value - cost_basis

        unrealized_pnl_percent = (
            unrealized_pnl / cost_basis if cost_basis != 0 else None
        )

        return PortfolioPositionValuation(
            position=position,
            cost_basis=cost_basis,
            quote=quote,
            quote_quality=freshness,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
        )

    @staticmethod
    def _assess_quote(
        quote: Quote | None,
        *,
        assessed_at: datetime,
        maximum_quote_age: timedelta,
    ) -> QuoteFreshness:
        """Safely assess quote freshness for downstream valuation."""

        try:
            return assess_quote_freshness(
                quote,
                assessed_at=assessed_at,
                maximum_age=maximum_quote_age,
            )
        except MarketDataQualityError:
            return QuoteFreshness(
                status="unavailable",
                observed_at=quote.timestamp if quote is not None else None,
                assessed_at=assessed_at,
                age_seconds=None,
                maximum_age_seconds=maximum_quote_age.total_seconds(),
                source=quote.source if quote is not None else None,
            )

    @staticmethod
    def _aggregate_quality(
        valuations: list[PortfolioPositionValuation],
    ) -> Literal["current", "stale", "unavailable", "empty"]:
        """Aggregate position quote quality without hiding stale data."""

        if not valuations:
            return "empty"

        statuses = {valuation.quote_quality.status for valuation in valuations}

        if statuses == {"fresh"}:
            return "current"

        if "fresh" in statuses or "stale" in statuses:
            return "stale"

        return "unavailable"

    @staticmethod
    def _build_currency_valuations(
        valuations: list[PortfolioPositionValuation],
    ) -> tuple[PortfolioCurrencyValuation, ...]:
        """Build currency-separated totals without cross-currency arithmetic."""

        grouped: dict[str, list[PortfolioPositionValuation]] = defaultdict(list)

        for valuation in valuations:
            grouped[valuation.position.currency].append(valuation)

        results: list[PortfolioCurrencyValuation] = []

        for currency in sorted(grouped):
            items = grouped[currency]

            cost_basis = sum(
                (item.cost_basis for item in items),
                Decimal("0"),
            )

            all_fresh = all(item.quote_quality.status == "fresh" for item in items)

            if all_fresh:
                market_value = sum(
                    (
                        item.market_value
                        for item in items
                        if item.market_value is not None
                    ),
                    Decimal("0"),
                )
                unrealized_pnl = market_value - cost_basis
            else:
                market_value = None
                unrealized_pnl = None

            statuses = {item.quote_quality.status for item in items}

            if statuses == {"fresh"}:
                quality = "current"
            elif "fresh" in statuses or "stale" in statuses:
                quality = "stale"
            else:
                quality = "unavailable"

            results.append(
                PortfolioCurrencyValuation(
                    currency=currency,
                    position_count=len(items),
                    quality=quality,
                    cost_basis=cost_basis,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                ),
            )

        return tuple(results)
