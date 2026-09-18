from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.market_data.service import MarketDataService
from app.portfolio.exposure_models import (
    PortfolioAssetClassExposure,
    PortfolioCurrencyExposure,
    PortfolioExposure,
    PortfolioPositionExposure,
)
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.valuation import PortfolioValuationService

ExposureQuality = Literal[
    "current",
    "stale",
    "unavailable",
    "empty",
]


class PortfolioExposureService:
    """Build deterministic exposure metrics from portfolio valuation."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
    ) -> None:
        self.valuation_service = PortfolioValuationService(
            persistence=persistence,
            market_data=market_data,
        )

    async def build(
        self,
        user_id: UUID,
        portfolio_id: UUID,
        *,
        assessed_at: datetime | None = None,
        maximum_quote_age: timedelta = timedelta(minutes=15),
    ) -> PortfolioExposure:
        """Build a quality-aware portfolio exposure analysis."""

        valuation = await self.valuation_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            assessed_at=assessed_at or datetime.now(UTC),
            maximum_quote_age=maximum_quote_age,
        )

        currency_valuations = {item.currency: item for item in valuation.currencies}

        position_exposures = tuple(
            self._build_position_exposure(
                valuation_position,
                currency_valuations,
            )
            for valuation_position in valuation.positions
        )

        asset_class_exposures = self._build_asset_class_exposures(
            valuation,
            currency_valuations,
        )

        return PortfolioExposure(
            portfolio=valuation.portfolio,
            assessed_at=valuation.assessed_at,
            maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
            quality=valuation.quality,
            currencies=tuple(
                self._build_currency_exposure(item) for item in valuation.currencies
            ),
            asset_classes=asset_class_exposures,
            positions=position_exposures,
        )

    @staticmethod
    def _build_currency_exposure(
        valuation,
    ) -> PortfolioCurrencyExposure:
        """Convert valuation currency totals into exposure totals."""

        return PortfolioCurrencyExposure(
            currency=valuation.currency,
            position_count=valuation.position_count,
            quality=valuation.quality,
            cost_basis=valuation.cost_basis,
            market_value=valuation.market_value,
        )

    @classmethod
    def _build_position_exposure(
        cls,
        valuation_position,
        currency_valuations,
    ) -> PortfolioPositionExposure:
        """Calculate one position's concentration within its own currency."""

        position = valuation_position.position
        currency_valuation = currency_valuations.get(
            position.currency,
        )

        weight = cls._calculate_weight(
            value=valuation_position.market_value,
            total=(
                currency_valuation.market_value
                if currency_valuation is not None
                else None
            ),
        )

        return PortfolioPositionExposure(
            position=position,
            cost_basis=valuation_position.cost_basis,
            market_value=valuation_position.market_value,
            market_value_weight=weight,
            quality=valuation_position.quote_quality.status,
        )

    @classmethod
    def _build_asset_class_exposures(
        cls,
        valuation,
        currency_valuations,
    ) -> tuple[PortfolioAssetClassExposure, ...]:
        """Aggregate exposure by currency and asset class."""

        grouped = defaultdict(list)

        for position_valuation in valuation.positions:
            key = (
                position_valuation.position.currency,
                position_valuation.position.asset_class,
            )
            grouped[key].append(position_valuation)

        results: list[PortfolioAssetClassExposure] = []

        for currency, asset_class in sorted(grouped):
            items = grouped[(currency, asset_class)]

            cost_basis = sum(
                (item.cost_basis for item in items),
                Decimal("0"),
            )

            all_current = all(
                item.quote_quality.status == "fresh" and item.market_value is not None
                for item in items
            )

            if all_current:
                market_value = sum(
                    (
                        item.market_value
                        for item in items
                        if item.market_value is not None
                    ),
                    Decimal("0"),
                )
            else:
                market_value = None

            currency_valuation = currency_valuations[currency]

            weight = cls._calculate_weight(
                value=market_value,
                total=currency_valuation.market_value,
            )

            results.append(
                PortfolioAssetClassExposure(
                    currency=currency,
                    asset_class=asset_class,
                    position_count=len(items),
                    quality=cls._aggregate_quality(
                        item.quote_quality.status for item in items
                    ),
                    cost_basis=cost_basis,
                    market_value=market_value,
                    market_value_weight=weight,
                ),
            )

        return tuple(results)

    @staticmethod
    def _calculate_weight(
        *,
        value: Decimal | None,
        total: Decimal | None,
    ) -> Decimal | None:
        """Calculate concentration only with a valid comparable basis."""

        if value is None or total is None or total == 0:
            return None

        return value / total

    @staticmethod
    def _aggregate_quality(
        statuses,
    ) -> ExposureQuality:
        """Aggregate quote states without treating partial data as current."""

        materialized = set(statuses)

        if materialized == {"fresh"}:
            return "current"

        if "fresh" in materialized or "stale" in materialized:
            return "stale"

        return "unavailable"
