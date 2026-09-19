from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from app.market_data.service import MarketDataService
from app.portfolio.models import PortfolioPosition
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_constraints_models import (
    PortfolioRiskConstraint,
    PortfolioRiskConstraintCurrency,
    PortfolioRiskConstraints,
)
from app.portfolio.valuation import PortfolioValuationService


class PortfolioRiskConstraintService:
    """Evaluate explicit concentration constraints on current portfolio state."""

    DEFAULT_MAXIMUM_POSITION_WEIGHT = Decimal("0.35")
    DEFAULT_MAXIMUM_ASSET_CLASS_WEIGHT = Decimal("0.60")

    _CONSTRAINT_NAMESPACE = UUID(
        "6d5d8d5d-4d7c-4a4b-9c2f-7f0af2b4ab01",
    )

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
        maximum_quote_age: timedelta,
        maximum_position_weight: Decimal = (DEFAULT_MAXIMUM_POSITION_WEIGHT),
        maximum_asset_class_weight: Decimal = (DEFAULT_MAXIMUM_ASSET_CLASS_WEIGHT),
        assessed_at: datetime | None = None,
    ) -> PortfolioRiskConstraints:
        """Evaluate position and asset-class concentration constraints."""

        self._validate_weight_limit(
            maximum_position_weight,
            "maximum_position_weight",
        )
        self._validate_weight_limit(
            maximum_asset_class_weight,
            "maximum_asset_class_weight",
        )

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
            return PortfolioRiskConstraints(
                portfolio=valuation.portfolio,
                assessed_at=valuation.assessed_at,
                maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
                maximum_position_weight=maximum_position_weight,
                maximum_asset_class_weight=maximum_asset_class_weight,
                quality="empty",
                evaluated_constraint_count=0,
                violation_count=0,
                currencies=(),
                constraints=(),
                methodology=self._methodology(),
                notes=(
                    "The portfolio has no current positions.",
                    "Risk constraints require current portfolio positions.",
                ),
            )

        positions_by_currency: dict[str, list] = defaultdict(list)

        for position_valuation in valuation.positions:
            positions_by_currency[position_valuation.position.currency].append(
                position_valuation
            )

        all_constraints: list[PortfolioRiskConstraint] = []
        currency_results: list[PortfolioRiskConstraintCurrency] = []

        current_currency_count = 0
        unavailable_currency_count = 0

        for currency in sorted(positions_by_currency):
            currency_positions = positions_by_currency[currency]

            has_complete_valuation = all(
                position_valuation.market_value is not None
                for position_valuation in currency_positions
            )

            if not has_complete_valuation:
                unavailable_currency_count += 1

                unavailable_constraints = self._build_unavailable_constraints(
                    currency_positions=currency_positions,
                    maximum_position_weight=maximum_position_weight,
                    maximum_asset_class_weight=maximum_asset_class_weight,
                )

                all_constraints.extend(unavailable_constraints)

                currency_results.append(
                    PortfolioRiskConstraintCurrency(
                        currency=currency,
                        position_count=len(currency_positions),
                        quality="unavailable",
                        current_market_value=None,
                        constraint_count=len(unavailable_constraints),
                        violation_count=0,
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

            currency_constraints = self._build_current_constraints(
                currency=currency,
                currency_positions=currency_positions,
                current_market_value=current_market_value,
                maximum_position_weight=maximum_position_weight,
                maximum_asset_class_weight=maximum_asset_class_weight,
            )

            all_constraints.extend(currency_constraints)

            currency_violation_count = sum(
                constraint.status == "violation" for constraint in currency_constraints
            )

            currency_results.append(
                PortfolioRiskConstraintCurrency(
                    currency=currency,
                    position_count=len(currency_positions),
                    quality="current",
                    current_market_value=current_market_value,
                    constraint_count=len(currency_constraints),
                    violation_count=currency_violation_count,
                ),
            )

        evaluated_constraint_count = sum(
            constraint.status != "unavailable" for constraint in all_constraints
        )

        violation_count = sum(
            constraint.status == "violation" for constraint in all_constraints
        )

        if current_currency_count == 0:
            quality = "none"
        elif unavailable_currency_count > 0:
            quality = "partial"
        else:
            quality = "sufficient"

        notes = [
            (
                "Maximum position weight is evaluated separately within each "
                "currency using current accepted market values."
            ),
            (
                "Maximum asset-class weight is evaluated separately within "
                "each currency using current accepted market values."
            ),
            (
                "A currency group is not partially evaluated when one or more "
                "of its positions lacks an accepted current quote."
            ),
            (
                "Risk constraints are diagnostic portfolio controls. They do "
                "not generate trades, return forecasts, or numerical event-risk "
                "scores."
            ),
        ]

        if violation_count > 0:
            notes.append(
                (
                    f"{violation_count} risk constraint(s) currently exceed "
                    "their configured limits."
                ),
            )

        if unavailable_currency_count > 0:
            notes.append(
                (
                    f"{unavailable_currency_count} currency group(s) could "
                    "not be fully evaluated because one or more positions "
                    "lacked an accepted current quote."
                ),
            )

        return PortfolioRiskConstraints(
            portfolio=valuation.portfolio,
            assessed_at=valuation.assessed_at,
            maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
            maximum_position_weight=maximum_position_weight,
            maximum_asset_class_weight=maximum_asset_class_weight,
            quality=quality,
            evaluated_constraint_count=evaluated_constraint_count,
            violation_count=violation_count,
            currencies=tuple(currency_results),
            constraints=tuple(all_constraints),
            methodology=self._methodology(),
            notes=tuple(notes),
        )

    @classmethod
    def _build_current_constraints(
        cls,
        *,
        currency: str,
        currency_positions,
        current_market_value: Decimal,
        maximum_position_weight: Decimal,
        maximum_asset_class_weight: Decimal,
    ) -> list[PortfolioRiskConstraint]:
        """Build all constraints for a fully valued currency group."""

        constraints: list[PortfolioRiskConstraint] = []

        asset_class_values: dict[str, Decimal] = defaultdict(
            lambda: Decimal("0"),
        )

        for position_valuation in currency_positions:
            market_value = position_valuation.market_value

            if market_value is None:
                raise RuntimeError(
                    "Current currency valuation is incomplete.",
                )

            asset_class_values[position_valuation.position.asset_class] += market_value

        if current_market_value <= 0:
            for position_valuation in currency_positions:
                position = position_valuation.position

                constraints.append(
                    cls._constraint(
                        seed=(f"position:{currency}:{position.position_id}"),
                        kind="maximum_position_weight",
                        scope="position",
                        currency=currency,
                        subject=position.symbol,
                        position=position,
                        asset_class=None,
                        observed_weight=None,
                        limit=maximum_position_weight,
                        status="unavailable",
                        rationale=(
                            "The currency has zero or negative market value, "
                            "so a position market-value weight cannot be "
                            "evaluated."
                        ),
                    ),
                )

            for asset_class in sorted(asset_class_values):
                constraints.append(
                    cls._constraint(
                        seed=f"asset-class:{currency}:{asset_class}",
                        kind="maximum_asset_class_weight",
                        scope="asset_class",
                        currency=currency,
                        subject=asset_class,
                        position=None,
                        asset_class=asset_class,
                        observed_weight=None,
                        limit=maximum_asset_class_weight,
                        status="unavailable",
                        rationale=(
                            "The currency has zero or negative market value, "
                            "so asset-class market-value weight cannot be "
                            "evaluated."
                        ),
                    ),
                )

            return constraints

        for position_valuation in currency_positions:
            position = position_valuation.position
            market_value = position_valuation.market_value

            if market_value is None:
                raise RuntimeError(
                    "Current position valuation is incomplete.",
                )

            observed_weight = market_value / current_market_value
            status = (
                "pass" if observed_weight <= maximum_position_weight else "violation"
            )
            headroom = maximum_position_weight - observed_weight

            constraints.append(
                cls._constraint(
                    seed=f"position:{currency}:{position.position_id}",
                    kind="maximum_position_weight",
                    scope="position",
                    currency=currency,
                    subject=position.symbol,
                    position=position,
                    asset_class=None,
                    observed_weight=observed_weight,
                    limit=maximum_position_weight,
                    status=status,
                    rationale=(
                        "Current position weight is compared with the "
                        "configured maximum position-weight constraint."
                    ),
                    headroom=headroom,
                ),
            )

        for asset_class in sorted(asset_class_values):
            asset_class_value = asset_class_values[asset_class]
            observed_weight = asset_class_value / current_market_value
            status = (
                "pass" if observed_weight <= maximum_asset_class_weight else "violation"
            )
            headroom = maximum_asset_class_weight - observed_weight

            constraints.append(
                cls._constraint(
                    seed=f"asset-class:{currency}:{asset_class}",
                    kind="maximum_asset_class_weight",
                    scope="asset_class",
                    currency=currency,
                    subject=asset_class,
                    position=None,
                    asset_class=asset_class,
                    observed_weight=observed_weight,
                    limit=maximum_asset_class_weight,
                    status=status,
                    rationale=(
                        "Current asset-class weight is compared with the "
                        "configured maximum asset-class-weight constraint."
                    ),
                    headroom=headroom,
                ),
            )

        return constraints

    @classmethod
    def _build_unavailable_constraints(
        cls,
        *,
        currency_positions,
        maximum_position_weight: Decimal,
        maximum_asset_class_weight: Decimal,
    ) -> list[PortfolioRiskConstraint]:
        """Build unavailable constraints for an incomplete currency group."""

        constraints: list[PortfolioRiskConstraint] = []
        asset_classes = {
            position_valuation.position.asset_class
            for position_valuation in currency_positions
        }

        currency = currency_positions[0].position.currency

        for position_valuation in currency_positions:
            position = position_valuation.position

            constraints.append(
                cls._constraint(
                    seed=f"position:{currency}:{position.position_id}",
                    kind="maximum_position_weight",
                    scope="position",
                    currency=currency,
                    subject=position.symbol,
                    position=position,
                    asset_class=None,
                    observed_weight=None,
                    limit=maximum_position_weight,
                    status="unavailable",
                    rationale=(
                        "The currency group contains at least one position "
                        "without an accepted current quote, so complete "
                        "position concentration cannot be evaluated."
                    ),
                ),
            )

        for asset_class in sorted(asset_classes):
            constraints.append(
                cls._constraint(
                    seed=f"asset-class:{currency}:{asset_class}",
                    kind="maximum_asset_class_weight",
                    scope="asset_class",
                    currency=currency,
                    subject=asset_class,
                    position=None,
                    asset_class=asset_class,
                    observed_weight=None,
                    limit=maximum_asset_class_weight,
                    status="unavailable",
                    rationale=(
                        "The currency group contains at least one position "
                        "without an accepted current quote, so complete "
                        "asset-class concentration cannot be evaluated."
                    ),
                ),
            )

        return constraints

    @classmethod
    def _constraint(
        cls,
        *,
        seed: str,
        kind,
        scope,
        currency: str,
        subject: str,
        position: PortfolioPosition | None,
        asset_class: str | None,
        observed_weight: Decimal | None,
        limit: Decimal,
        status,
        rationale: str,
        headroom: Decimal | None = None,
    ) -> PortfolioRiskConstraint:
        """Create a stable identifier for a deterministic constraint."""

        return PortfolioRiskConstraint(
            constraint_id=uuid5(
                cls._CONSTRAINT_NAMESPACE,
                seed,
            ),
            kind=kind,
            scope=scope,
            currency=currency,
            subject=subject,
            position=position,
            asset_class=asset_class,
            observed_weight=observed_weight,
            limit=limit,
            headroom=headroom,
            status=status,
            rationale=rationale,
        )

    @staticmethod
    def _validate_weight_limit(
        value: Decimal,
        label: str,
    ) -> None:
        """Validate a weight constraint."""

        if value <= 0 or value > 1:
            raise ValueError(
                f"{label} must be greater than 0 and at most 1",
            )

    @staticmethod
    def _methodology() -> str:
        """Describe the risk-constraint methodology."""

        return (
            "Risk constraints evaluate current portfolio concentration using "
            "accepted market values from the quality-aware portfolio "
            "valuation. Position and asset-class weights are calculated "
            "separately within each currency because the portfolio does not "
            "currently provide a base-currency FX conversion layer. A "
            "maximum-position-weight constraint and a maximum-asset-class-"
            "weight constraint are evaluated against explicit user-request "
            "limits. Constraint violations describe current portfolio state "
            "and do not forecast returns or generate trades."
        )
