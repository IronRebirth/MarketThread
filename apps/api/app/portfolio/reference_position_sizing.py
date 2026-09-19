from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from app.market_data.service import MarketDataService
from app.portfolio.models import PortfolioPosition
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.reference_position_sizing_models import (
    PortfolioReferenceCurrencySizing,
    PortfolioReferencePositionSizing,
    PortfolioReferencePositionSizingItem,
)
from app.portfolio.valuation import PortfolioValuationService


class PortfolioReferencePositionSizingService:
    """Build a deterministic reference sizing baseline from portfolio valuation."""

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
        assessed_at: datetime | None = None,
    ) -> PortfolioReferencePositionSizing:
        """Build equal-reference sizing without combining currencies."""

        valuation_service = PortfolioValuationService(
            persistence=self.persistence,
            market_data=self.market_data,
        )

        valuation = await valuation_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            maximum_quote_age=maximum_quote_age,
            assessed_at=assessed_at,
        )

        if not valuation.positions:
            return PortfolioReferencePositionSizing(
                portfolio=valuation.portfolio,
                assessed_at=valuation.assessed_at,
                maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
                quality="empty",
                positions=(),
                currencies=(),
                methodology=self._methodology(),
                notes=(
                    "The portfolio has no current positions.",
                    "Reference sizing requires current portfolio positions.",
                ),
            )

        positions_by_currency: dict[str, list] = defaultdict(list)

        for position_valuation in valuation.positions:
            positions_by_currency[position_valuation.position.currency].append(
                position_valuation
            )

        currency_results: list[PortfolioReferenceCurrencySizing] = []
        position_results: list[PortfolioReferencePositionSizingItem] = []

        current_currency_count = 0
        unavailable_currency_count = 0

        for currency in sorted(positions_by_currency):
            currency_positions = positions_by_currency[currency]
            position_count = len(currency_positions)
            reference_weight = Decimal("1") / Decimal(position_count)

            valuation_complete = all(
                position_valuation.market_value is not None
                and position_valuation.quote is not None
                for position_valuation in currency_positions
            )

            if not valuation_complete:
                unavailable_currency_count += 1

                currency_results.append(
                    PortfolioReferenceCurrencySizing(
                        currency=currency,
                        position_count=position_count,
                        quality="unavailable",
                        current_market_value=None,
                        reference_weight=reference_weight,
                        reference_market_value=None,
                    ),
                )

                for position_valuation in currency_positions:
                    position_results.append(
                        self._build_unavailable_item(
                            position=position_valuation.position,
                            position_count=position_count,
                            reference_weight=reference_weight,
                            note=(
                                "Reference value and quantity are unavailable "
                                "because at least one position in this "
                                f"{currency} currency group lacks an accepted "
                                "current quote."
                            ),
                        ),
                    )

                continue

            current_currency_count += 1

            current_market_value = sum(
                (
                    position_valuation.market_value
                    for position_valuation in currency_positions
                    if position_valuation.market_value is not None
                ),
                Decimal("0"),
            )

            reference_market_value = current_market_value * reference_weight

            currency_results.append(
                PortfolioReferenceCurrencySizing(
                    currency=currency,
                    position_count=position_count,
                    quality="current",
                    current_market_value=current_market_value,
                    reference_weight=reference_weight,
                    reference_market_value=reference_market_value,
                ),
            )

            for position_valuation in currency_positions:
                position = position_valuation.position
                current_market_value_for_position = position_valuation.market_value

                current_weight = (
                    current_market_value_for_position / current_market_value
                    if current_market_value != 0
                    and current_market_value_for_position is not None
                    else None
                )

                quote_price = (
                    position_valuation.quote.price
                    if position_valuation.quote is not None
                    else None
                )

                reference_quantity = (
                    reference_market_value / quote_price
                    if quote_price is not None and quote_price > 0
                    else None
                )

                quantity_delta = (
                    reference_quantity - position.quantity
                    if reference_quantity is not None
                    else None
                )

                notes: list[str] = [
                    (
                        "Reference weight is equal-weighted within this "
                        f"{currency} currency group."
                    ),
                    (
                        "Reference quantity is calculated from reference "
                        "market value divided by the accepted current quote."
                    ),
                ]

                if current_market_value == 0:
                    notes.append(
                        (
                            "Current currency market value is zero, so a "
                            "current position weight cannot be calculated."
                        ),
                    )

                position_results.append(
                    PortfolioReferencePositionSizingItem(
                        position=position,
                        currency=currency,
                        position_count=position_count,
                        quality="current",
                        current_market_value=current_market_value_for_position,
                        current_weight=current_weight,
                        reference_weight=reference_weight,
                        reference_market_value=reference_market_value,
                        reference_quantity=reference_quantity,
                        quantity_delta=quantity_delta,
                        quote_price=quote_price,
                        notes=tuple(notes),
                    ),
                )

        if current_currency_count == 0:
            quality = "none"
        elif unavailable_currency_count == 0:
            quality = "sufficient"
        else:
            quality = "partial"

        notes = [
            (
                "Reference sizing uses an equal-weight baseline of 1/N for "
                "each current position within its own currency."
            ),
            (
                "Currencies are kept separate because the portfolio does "
                "not currently provide a base-currency FX conversion layer."
            ),
            (
                "Reference sizing is a transparent allocation benchmark; "
                "it is not a return forecast, risk score, or guaranteed "
                "trade recommendation."
            ),
        ]

        if unavailable_currency_count > 0:
            notes.append(
                (
                    f"{unavailable_currency_count} currency group(s) could "
                    "not be sized because one or more positions lacked an "
                    "accepted current quote."
                ),
            )

        return PortfolioReferencePositionSizing(
            portfolio=valuation.portfolio,
            assessed_at=valuation.assessed_at,
            maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
            quality=quality,
            positions=tuple(position_results),
            currencies=tuple(currency_results),
            methodology=self._methodology(),
            notes=tuple(notes),
        )

    @staticmethod
    def _build_unavailable_item(
        *,
        position: PortfolioPosition,
        position_count: int,
        reference_weight: Decimal,
        note: str,
    ) -> PortfolioReferencePositionSizingItem:
        """Build an item when the currency group cannot be valued."""

        return PortfolioReferencePositionSizingItem(
            position=position,
            currency=position.currency,
            position_count=position_count,
            quality="unavailable",
            current_market_value=None,
            current_weight=None,
            reference_weight=reference_weight,
            reference_market_value=None,
            reference_quantity=None,
            quantity_delta=None,
            quote_price=None,
            notes=(note,),
        )

    @staticmethod
    def _methodology() -> str:
        """Describe the reference position sizing methodology."""

        return (
            "Equal-reference position sizing within each portfolio currency. "
            "For a currency containing N current positions, each position "
            "receives a reference weight of 1/N. When every position in that "
            "currency has an accepted current quote, the currency market "
            "value is divided equally across its positions and the reference "
            "quantity is calculated from reference market value divided by "
            "the current quote price. Currencies are never combined or "
            "converted. The result is an allocation benchmark, not a return "
            "forecast or numerical risk recommendation."
        )
