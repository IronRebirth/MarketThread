from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.market_data.service import MarketDataService
from app.portfolio.exposure import PortfolioExposureService
from app.portfolio.exposure_models import PortfolioExposure
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_indicators_models import (
    PortfolioRiskIndicator,
    PortfolioRiskIndicators,
)


class PortfolioRiskIndicatorService:
    """Build deterministic portfolio risk observations."""

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
    ) -> None:
        self.exposure_service = PortfolioExposureService(
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
    ) -> PortfolioRiskIndicators:
        """Build risk observations from the quality-aware exposure layer."""

        exposure = await self.exposure_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            assessed_at=assessed_at or datetime.now(UTC),
            maximum_quote_age=maximum_quote_age,
        )

        indicators = self._build_indicators(exposure)

        return PortfolioRiskIndicators(
            portfolio=exposure.portfolio,
            assessed_at=exposure.assessed_at,
            maximum_quote_age_seconds=exposure.maximum_quote_age_seconds,
            quality=exposure.quality,
            indicators=indicators,
        )

    @staticmethod
    def _build_indicators(
        exposure: PortfolioExposure,
    ) -> tuple[PortfolioRiskIndicator, ...]:
        """Derive structural and data-quality observations."""

        indicators: list[PortfolioRiskIndicator] = []

        if exposure.quality in {"stale", "unavailable"}:
            indicators.append(
                PortfolioRiskIndicator(
                    kind="valuation_data_quality",
                    level="attention",
                    currency=None,
                    title="Valuation coverage is incomplete",
                    rationale=(
                        "Some portfolio positions do not have sufficiently "
                        "fresh market quotes, so complete current-market "
                        "concentration cannot be established."
                    ),
                    position_count=len(exposure.positions),
                    asset_class=None,
                ),
            )

        for currency in exposure.currencies:
            if currency.position_count == 1:
                indicators.append(
                    PortfolioRiskIndicator(
                        kind="single_instrument_currency_exposure",
                        level="attention",
                        currency=currency.currency,
                        title=(f"Single-instrument exposure in {currency.currency}"),
                        rationale=(
                            "Only one persisted position is represented "
                            f"within the {currency.currency} currency bucket. "
                            "This is a structural concentration observation, "
                            "not a forecast of loss."
                        ),
                        position_count=currency.position_count,
                        asset_class=None,
                    ),
                )

        currency_position_counts = {
            currency.currency: currency.position_count
            for currency in exposure.currencies
        }

        for asset_class in exposure.asset_classes:
            currency_position_count = currency_position_counts.get(
                asset_class.currency,
            )

            if (
                currency_position_count is not None
                and currency_position_count > 1
                and asset_class.position_count == currency_position_count
            ):
                indicators.append(
                    PortfolioRiskIndicator(
                        kind="single_asset_class_currency_exposure",
                        level="attention",
                        currency=asset_class.currency,
                        title=(f"Single asset class in {asset_class.currency}"),
                        rationale=(
                            f"All {asset_class.position_count} positions in "
                            f"{asset_class.currency} are classified as "
                            f"{asset_class.asset_class}. This describes "
                            "limited asset-class diversification within the "
                            "currency bucket."
                        ),
                        position_count=asset_class.position_count,
                        asset_class=asset_class.asset_class,
                    ),
                )

        return tuple(indicators)
