from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.db.models.instrument import Instrument
from app.market_data.models import Bar
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.service import MarketDataService
from app.portfolio.models import Portfolio, PortfolioPosition
from app.portfolio.performance_models import (
    PerformanceQuality,
    PortfolioCurrencyPerformance,
    PortfolioPerformance,
    PortfolioPerformancePoint,
)
from app.portfolio.persistence import PortfolioPersistenceService


class PortfolioPerformanceService:
    """Build historical portfolio value and return series."""

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
        lookback_days: int = 365,
    ) -> PortfolioPerformance:
        """Build currency-separated historical portfolio performance."""

        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than zero")

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
            "assessed_at",
        )

        assessment_time = assessment_time.astimezone(UTC)
        lookback_start = assessment_time - timedelta(days=lookback_days)

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

        positions = await self._build_positions(position_records)

        if not positions:
            return PortfolioPerformance(
                portfolio=portfolio,
                assessed_at=assessment_time,
                lookback_start=lookback_start,
                lookback_end=assessment_time,
                lookback_days=lookback_days,
                position_count=0,
                quality="empty",
                methodology=self._methodology(),
                currencies=(),
            )

        grouped_positions: dict[str, list[PortfolioPosition]] = defaultdict(list)

        for position in positions:
            grouped_positions[position.currency].append(position)

        currencies: list[PortfolioCurrencyPerformance] = []

        for currency in sorted(grouped_positions):
            currency_performance = await self._build_currency_performance(
                currency=currency,
                positions=tuple(grouped_positions[currency]),
                start_at=lookback_start,
                end_at=assessment_time,
            )
            currencies.append(currency_performance)

        currency_results = tuple(currencies)

        return PortfolioPerformance(
            portfolio=portfolio,
            assessed_at=assessment_time,
            lookback_start=lookback_start,
            lookback_end=assessment_time,
            lookback_days=lookback_days,
            position_count=position_count,
            quality=self._aggregate_quality(currency_results),
            methodology=self._methodology(),
            currencies=currency_results,
        )

    async def _build_positions(
        self,
        position_records,
    ) -> tuple[PortfolioPosition, ...]:
        """Resolve canonical instrument metadata for persisted positions."""

        positions: list[PortfolioPosition] = []

        for position_record in position_records:
            instrument = await self.persistence.session.get(
                Instrument,
                position_record.instrument_id,
            )

            if instrument is None:
                raise RuntimeError(
                    "Portfolio position references a missing instrument.",
                )

            positions.append(
                PortfolioPosition(
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
                ),
            )

        return tuple(positions)

    async def _build_currency_performance(
        self,
        *,
        currency: str,
        positions: tuple[PortfolioPosition, ...],
        start_at: datetime,
        end_at: datetime,
    ) -> PortfolioCurrencyPerformance:
        """Build a historical value series from common observation dates."""

        position_histories: list[
            tuple[
                PortfolioPosition,
                dict[date, tuple[datetime, Decimal]],
                set[str],
            ]
        ] = []

        unavailable_symbols: list[str] = []

        for position in positions:
            try:
                bars = await self.market_data.get_historical_bars(
                    position.instrument_id,
                    start_at,
                    end_at,
                )
            except MarketDataProviderError:
                bars = ()

            daily_bars, sources = self._select_daily_closes(bars)

            if not daily_bars:
                unavailable_symbols.append(position.symbol)

            position_histories.append(
                (
                    position,
                    daily_bars,
                    sources,
                ),
            )

        common_days: set[date] | None = None

        for _position, daily_bars, _sources in position_histories:
            observed_days = set(daily_bars)

            if common_days is None:
                common_days = observed_days
            else:
                common_days &= observed_days

        complete_days = sorted(common_days or [])

        sources = tuple(
            sorted(
                {
                    source
                    for _position, _daily_bars, position_sources in position_histories
                    for source in position_sources
                },
            )
        )

        if not complete_days:
            notes = [
                (
                    "No dates have complete historical close coverage for every "
                    "position in this currency."
                ),
            ]

            if unavailable_symbols:
                notes.append(
                    "Historical bars were unavailable for: "
                    + ", ".join(sorted(unavailable_symbols))
                    + ".",
                )

            return PortfolioCurrencyPerformance(
                currency=currency,
                position_count=len(positions),
                quality="unavailable",
                first_observed_on=None,
                last_observed_on=None,
                observation_count=0,
                return_count=0,
                initial_value=None,
                latest_value=None,
                period_return=None,
                points=(),
                sources=sources,
                notes=tuple(notes),
            )

        points: list[PortfolioPerformancePoint] = []

        for observed_day in complete_days:
            portfolio_value = Decimal("0")

            for position, daily_bars, _sources in position_histories:
                _, close = daily_bars[observed_day]
                portfolio_value += position.quantity * close

            points.append(
                PortfolioPerformancePoint(
                    observed_on=observed_day,
                    value=portfolio_value,
                ),
            )

        initial_value = points[0].value
        latest_value = points[-1].value

        period_return: Decimal | None = None

        if initial_value > 0 and len(points) >= 2:
            period_return = (latest_value / initial_value) - Decimal("1")

        notes = [
            "Current quantities are held constant across the lookback window.",
            "No synthetic prices are created for missing historical observations.",
            (
                "Portfolio values are calculated separately for each currency; "
                "no FX conversion is performed."
            ),
            (
                "Only dates with historical closes for every position in the "
                "currency are included."
            ),
        ]

        if len(points) < 2:
            quality: PerformanceQuality = "insufficient"
            notes.append(
                "At least two complete observations are required to calculate "
                "period return."
            )
        else:
            quality = "sufficient"

        return PortfolioCurrencyPerformance(
            currency=currency,
            position_count=len(positions),
            quality=quality,
            first_observed_on=complete_days[0],
            last_observed_on=complete_days[-1],
            observation_count=len(points),
            return_count=max(len(points) - 1, 0),
            initial_value=initial_value,
            latest_value=latest_value,
            period_return=period_return,
            points=tuple(points),
            sources=sources,
            notes=tuple(notes),
        )

    @staticmethod
    def _select_daily_closes(
        bars: Sequence[Bar],
    ) -> tuple[
        dict[date, tuple[datetime, Decimal]],
        set[str],
    ]:
        """Reduce historical bars to the final close on each UTC date."""

        daily_bars: dict[date, tuple[datetime, Decimal]] = {}
        sources: set[str] = set()

        for bar in bars:
            timestamp = bar.timestamp.astimezone(UTC)
            observed_day = timestamp.date()

            current = daily_bars.get(observed_day)

            if current is None or timestamp > current[0]:
                daily_bars[observed_day] = (
                    timestamp,
                    bar.close,
                )

            sources.add(bar.source)

        return daily_bars, sources

    @staticmethod
    def _aggregate_quality(
        currencies: tuple[PortfolioCurrencyPerformance, ...],
    ) -> PerformanceQuality:
        """Aggregate currency quality without hiding insufficient data."""

        if not currencies:
            return "empty"

        qualities = {item.quality for item in currencies}

        if qualities == {"sufficient"}:
            return "sufficient"

        if qualities == {"unavailable"}:
            return "unavailable"

        return "insufficient"

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        label: str,
    ) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

    @staticmethod
    def _methodology() -> str:
        """Describe the historical portfolio-performance methodology."""

        return (
            "Constant-position historical proxy using current persisted quantities, "
            "daily closing prices, and simple period return between the first and "
            "latest complete observations."
        )
