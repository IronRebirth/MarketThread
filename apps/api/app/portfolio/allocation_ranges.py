from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from app.market_data.service import MarketDataService
from app.portfolio.allocation_ranges_models import (
    PortfolioAllocationCurrencyRange,
    PortfolioAllocationRangeItem,
    PortfolioAllocationRanges,
)
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.reference_position_sizing import (
    PortfolioReferencePositionSizingService,
)


class PortfolioAllocationRangeService:
    """Build deterministic allocation ranges from reference position sizing."""

    DEFAULT_RANGE_TOLERANCE = Decimal("0.25")

    def __init__(
        self,
        persistence: PortfolioPersistenceService,
        market_data: MarketDataService,
    ) -> None:
        self.persistence = persistence
        self.market_data = market_data

    async def build(
        self,
        user_id,
        portfolio_id,
        *,
        maximum_quote_age: timedelta,
        range_tolerance: Decimal = DEFAULT_RANGE_TOLERANCE,
        assessed_at: datetime | None = None,
    ) -> PortfolioAllocationRanges:
        """Build allocation ranges within each portfolio currency."""

        self._validate_range_tolerance(range_tolerance)

        reference_service = PortfolioReferencePositionSizingService(
            persistence=self.persistence,
            market_data=self.market_data,
        )

        reference = await reference_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            maximum_quote_age=maximum_quote_age,
            assessed_at=assessed_at,
        )

        if reference.quality == "empty":
            return PortfolioAllocationRanges(
                portfolio=reference.portfolio,
                assessed_at=reference.assessed_at,
                maximum_quote_age_seconds=reference.maximum_quote_age_seconds,
                range_tolerance=range_tolerance,
                quality="empty",
                positions=(),
                currencies=(),
                methodology=self._methodology(),
                notes=(
                    "The portfolio has no current positions.",
                    "Allocation ranges require current portfolio positions.",
                ),
            )

        positions_by_currency: dict[str, list] = defaultdict(list)

        for item in reference.positions:
            positions_by_currency[item.currency].append(item)

        position_results: list[PortfolioAllocationRangeItem] = []
        currency_results: list[PortfolioAllocationCurrencyRange] = []

        current_currency_count = 0
        unavailable_currency_count = 0

        for currency in sorted(positions_by_currency):
            currency_items = positions_by_currency[currency]
            currency_reference_items = [
                item for item in currency_items if item.quality == "current"
            ]

            if not currency_items or len(currency_reference_items) != len(
                currency_items
            ):
                unavailable_currency_count += 1

                target_weight = currency_items[0].reference_weight
                minimum_weight, maximum_weight = self._calculate_range(
                    target_weight,
                    range_tolerance,
                )

                currency_results.append(
                    PortfolioAllocationCurrencyRange(
                        currency=currency,
                        position_count=len(currency_items),
                        quality="unavailable",
                        current_market_value=None,
                        minimum_weight=minimum_weight,
                        target_weight=target_weight,
                        maximum_weight=maximum_weight,
                        minimum_market_value=None,
                        target_market_value=None,
                        maximum_market_value=None,
                    ),
                )

                for item in currency_items:
                    position_results.append(
                        self._build_unavailable_item(
                            item=item,
                            range_tolerance=range_tolerance,
                        ),
                    )

                continue

            current_currency_count += 1

            current_market_value = sum(
                (
                    item.current_market_value
                    for item in currency_items
                    if item.current_market_value is not None
                ),
                Decimal("0"),
            )

            target_weight = currency_items[0].reference_weight

            minimum_weight, maximum_weight = self._calculate_range(
                target_weight,
                range_tolerance,
            )

            minimum_market_value = current_market_value * minimum_weight
            target_market_value = current_market_value * target_weight
            maximum_market_value = current_market_value * maximum_weight

            currency_results.append(
                PortfolioAllocationCurrencyRange(
                    currency=currency,
                    position_count=len(currency_items),
                    quality="current",
                    current_market_value=current_market_value,
                    minimum_weight=minimum_weight,
                    target_weight=target_weight,
                    maximum_weight=maximum_weight,
                    minimum_market_value=minimum_market_value,
                    target_market_value=target_market_value,
                    maximum_market_value=maximum_market_value,
                ),
            )

            for item in currency_items:
                position_results.append(
                    self._build_current_item(
                        item=item,
                        current_market_value=current_market_value,
                        minimum_weight=minimum_weight,
                        target_weight=target_weight,
                        maximum_weight=maximum_weight,
                        minimum_market_value=minimum_market_value,
                        target_market_value=target_market_value,
                        maximum_market_value=maximum_market_value,
                        range_tolerance=range_tolerance,
                    ),
                )

        if current_currency_count == 0:
            quality = "none"
        elif unavailable_currency_count > 0:
            quality = "partial"
        else:
            quality = "sufficient"

        notes = [
            (
                "Each position receives the equal-weight reference target "
                "from the portfolio reference-sizing baseline."
            ),
            (
                f"Minimum and maximum weights are set at {range_tolerance} "
                "relative tolerance below and above the target, respectively."
            ),
            (
                "Allocation weights are calculated separately within each "
                "currency; currencies are never combined or converted."
            ),
            (
                "Allocation ranges are transparent benchmarks and do not "
                "constitute automated trade instructions or return forecasts."
            ),
        ]

        if unavailable_currency_count > 0:
            notes.append(
                (
                    f"{unavailable_currency_count} currency group(s) could "
                    "not produce current allocation values because one or "
                    "more positions lacked an accepted quote."
                ),
            )

        return PortfolioAllocationRanges(
            portfolio=reference.portfolio,
            assessed_at=reference.assessed_at,
            maximum_quote_age_seconds=reference.maximum_quote_age_seconds,
            range_tolerance=range_tolerance,
            quality=quality,
            positions=tuple(position_results),
            currencies=tuple(currency_results),
            methodology=self._methodology(),
            notes=tuple(notes),
        )

    @staticmethod
    def _calculate_range(
        target_weight: Decimal,
        range_tolerance: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Calculate bounded relative minimum and maximum weights."""

        minimum_weight = target_weight * (Decimal("1") - range_tolerance)
        maximum_weight = target_weight * (Decimal("1") + range_tolerance)

        minimum_weight = max(
            Decimal("0"),
            minimum_weight,
        )
        maximum_weight = min(
            Decimal("1"),
            maximum_weight,
        )

        return minimum_weight, maximum_weight

    @staticmethod
    def _build_current_item(
        *,
        item,
        current_market_value: Decimal,
        minimum_weight: Decimal,
        target_weight: Decimal,
        maximum_weight: Decimal,
        minimum_market_value: Decimal,
        target_market_value: Decimal,
        maximum_market_value: Decimal,
        range_tolerance: Decimal,
    ) -> PortfolioAllocationRangeItem:
        """Build a range item for a currently valued position."""

        current_weight = item.current_weight

        within_range = (
            None
            if current_weight is None
            else minimum_weight <= current_weight <= maximum_weight
        )

        notes = [
            (
                f"Range uses a {range_tolerance} relative tolerance around "
                "the equal-weight reference target."
            ),
            (
                "Current weight is measured against the total current "
                f"{item.currency} portfolio market value."
            ),
        ]

        if within_range is False:
            notes.append(
                (
                    "The current position weight is outside the "
                    "reference allocation range."
                ),
            )

        return PortfolioAllocationRangeItem(
            position=item.position,
            currency=item.currency,
            position_count=item.position_count,
            quality="current",
            current_market_value=(
                current_market_value if item.current_market_value is not None else None
            ),
            current_weight=current_weight,
            minimum_weight=minimum_weight,
            target_weight=target_weight,
            maximum_weight=maximum_weight,
            minimum_market_value=minimum_market_value,
            target_market_value=target_market_value,
            maximum_market_value=maximum_market_value,
            within_range=within_range,
            notes=tuple(notes),
        )

    @staticmethod
    def _build_unavailable_item(
        *,
        item,
        range_tolerance: Decimal,
    ) -> PortfolioAllocationRangeItem:
        """Build a range item when its currency cannot be valued."""

        minimum_weight, maximum_weight = (
            PortfolioAllocationRangeService._calculate_range(
                item.reference_weight,
                range_tolerance,
            )
        )

        return PortfolioAllocationRangeItem(
            position=item.position,
            currency=item.currency,
            position_count=item.position_count,
            quality="unavailable",
            current_market_value=None,
            current_weight=None,
            minimum_weight=minimum_weight,
            target_weight=item.reference_weight,
            maximum_weight=maximum_weight,
            minimum_market_value=None,
            target_market_value=None,
            maximum_market_value=None,
            within_range=None,
            notes=(
                (
                    "Allocation market values cannot be calculated because "
                    f"the {item.currency} currency group does not have "
                    "accepted current quotes for every position."
                ),
                (
                    "The target and range weights remain visible as "
                    "reference benchmarks."
                ),
            ),
        )

    @staticmethod
    def _validate_range_tolerance(
        range_tolerance: Decimal,
    ) -> None:
        """Validate the relative allocation-range tolerance."""

        if range_tolerance <= 0 or range_tolerance > 1:
            raise ValueError(
                "range_tolerance must be greater than 0 and at most 1",
            )

    @staticmethod
    def _methodology() -> str:
        """Describe the allocation-range methodology."""

        return (
            "Allocation ranges are derived from the deterministic equal-weight "
            "reference sizing baseline. For a target weight T and relative "
            "range tolerance R, the minimum is max(0, T × (1 − R)) and the "
            "maximum is min(1, T × (1 + R)). Current, target, minimum, and "
            "maximum market values are calculated separately within each "
            "currency using the currency's current accepted market value. "
            "Currencies are never combined or converted. The result is an "
            "allocation benchmark rather than a return forecast or automated "
            "trade instruction."
        )
