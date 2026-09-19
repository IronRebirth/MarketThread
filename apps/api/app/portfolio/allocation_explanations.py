from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.market_data.service import MarketDataService
from app.portfolio.allocation_explanations_models import (
    PortfolioAllocationExplanationCurrency,
    PortfolioAllocationExplanationItem,
    PortfolioAllocationExplanations,
)
from app.portfolio.allocation_ranges import PortfolioAllocationRangeService
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_constraints import PortfolioRiskConstraintService


class PortfolioAllocationExplanationService:
    """Build deterministic explanations from allocation ranges and constraints."""

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
        range_tolerance=None,
        maximum_position_weight=None,
        maximum_asset_class_weight=None,
        assessed_at: datetime | None = None,
    ) -> PortfolioAllocationExplanations:
        """Explain current allocation state for a user-owned portfolio."""

        assessment_time = assessed_at or datetime.now(UTC)

        self._validate_aware_datetime(
            assessment_time,
        )

        range_service = PortfolioAllocationRangeService(
            persistence=self.persistence,
            market_data=self.market_data,
        )

        ranges = await range_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            maximum_quote_age=maximum_quote_age,
            range_tolerance=(
                range_tolerance
                if range_tolerance is not None
                else range_service.DEFAULT_RANGE_TOLERANCE
            ),
            assessed_at=assessment_time,
        )

        constraint_service = PortfolioRiskConstraintService(
            persistence=self.persistence,
            market_data=self.market_data,
        )

        constraints = await constraint_service.build(
            user_id=user_id,
            portfolio_id=portfolio_id,
            maximum_quote_age=maximum_quote_age,
            maximum_position_weight=(
                maximum_position_weight
                if maximum_position_weight is not None
                else constraint_service.DEFAULT_MAXIMUM_POSITION_WEIGHT
            ),
            maximum_asset_class_weight=(
                maximum_asset_class_weight
                if maximum_asset_class_weight is not None
                else constraint_service.DEFAULT_MAXIMUM_ASSET_CLASS_WEIGHT
            ),
            assessed_at=assessment_time,
        )

        if ranges.quality == "empty":
            return PortfolioAllocationExplanations(
                portfolio=ranges.portfolio,
                assessed_at=ranges.assessed_at,
                maximum_quote_age_seconds=ranges.maximum_quote_age_seconds,
                range_tolerance=ranges.range_tolerance,
                maximum_position_weight=(constraints.maximum_position_weight),
                maximum_asset_class_weight=(constraints.maximum_asset_class_weight),
                quality="empty",
                explanation_count=0,
                outside_range_count=0,
                violation_count=0,
                currencies=(),
                items=(),
                methodology=self._methodology(),
                notes=(
                    "The portfolio has no current positions.",
                    "Allocation explanations require current portfolio positions.",
                ),
            )

        constraint_violations_by_position = defaultdict(list)
        constraint_violations_by_asset_class = defaultdict(list)

        for constraint in constraints.constraints:
            if constraint.status != "violation":
                continue

            if constraint.position is not None:
                constraint_violations_by_position[
                    constraint.position.position_id
                ].append(constraint)
            elif constraint.asset_class is not None:
                constraint_violations_by_asset_class[
                    (
                        constraint.currency,
                        constraint.asset_class,
                    )
                ].append(constraint)

        items: list[PortfolioAllocationExplanationItem] = []

        for range_item in ranges.positions:
            position = range_item.position

            position_violations = list(
                constraint_violations_by_position.get(
                    position.position_id,
                    [],
                ),
            )

            asset_class_violations = list(
                constraint_violations_by_asset_class.get(
                    (
                        range_item.currency,
                        position.asset_class,
                    ),
                    [],
                ),
            )

            violations = [
                *position_violations,
                *asset_class_violations,
            ]

            violated_constraints = tuple(
                dict.fromkeys(constraint.kind for constraint in violations),
            )

            status = self._determine_status(range_item)

            explanation = self._build_position_explanation(
                range_item=range_item,
                status=status,
                violations=violations,
            )

            notes = list(range_item.notes)

            if violations:
                notes.append(
                    (
                        f"{len(violations)} configured risk constraint(s) "
                        "are currently violated for this position or its "
                        "asset class."
                    ),
                )

            items.append(
                PortfolioAllocationExplanationItem(
                    position=position,
                    currency=range_item.currency,
                    position_count=range_item.position_count,
                    quality=(
                        "current" if range_item.quality == "current" else "unavailable"
                    ),
                    status=status,
                    current_market_value=range_item.current_market_value,
                    current_weight=range_item.current_weight,
                    minimum_weight=range_item.minimum_weight,
                    target_weight=range_item.target_weight,
                    maximum_weight=range_item.maximum_weight,
                    constraint_violation_count=len(violations),
                    violated_constraints=violated_constraints,
                    explanation=explanation,
                    notes=tuple(notes),
                ),
            )

        positions_by_currency: dict[str, list] = defaultdict(list)

        for item in items:
            positions_by_currency[item.currency].append(item)

        currency_results: list[PortfolioAllocationExplanationCurrency] = []

        for currency in sorted(positions_by_currency):
            currency_items = positions_by_currency[currency]

            outside_range_count = sum(
                item.status in {"below_minimum", "above_maximum"}
                for item in currency_items
            )

            unique_currency_violation_ids = {
                constraint.constraint_id
                for constraint in constraints.constraints
                if (
                    constraint.status == "violation" and constraint.currency == currency
                )
            }

            violation_count = len(unique_currency_violation_ids)

            quality = (
                "current"
                if all(item.quality == "current" for item in currency_items)
                else "unavailable"
            )

            explanation = self._build_currency_explanation(
                currency=currency,
                currency_items=currency_items,
                outside_range_count=outside_range_count,
                violation_count=violation_count,
            )

            currency_results.append(
                PortfolioAllocationExplanationCurrency(
                    currency=currency,
                    position_count=len(currency_items),
                    quality=quality,
                    explanation_count=len(currency_items),
                    outside_range_count=outside_range_count,
                    violation_count=violation_count,
                    explanation=explanation,
                ),
            )

        outside_range_count = sum(
            item.status in {"below_minimum", "above_maximum"} for item in items
        )

        unique_violation_ids = {
            constraint.constraint_id
            for constraint in constraints.constraints
            if constraint.status == "violation"
        }

        violation_count = len(unique_violation_ids)
        explanation_count = len(items)

        if ranges.quality == "sufficient" and constraints.quality == "sufficient":
            quality = "sufficient"
        elif ranges.quality == "partial" or constraints.quality == "partial":
            quality = "partial"
        else:
            quality = "none"

        notes = [
            (
                "Explanations describe current allocation state using the "
                "existing reference ranges and explicit risk constraints."
            ),
            (
                "A position can be outside its allocation range without "
                "necessarily violating a configured risk constraint."
            ),
            (
                "Risk-constraint violations are attributed to the affected "
                "position or its currency-specific asset class."
            ),
            (
                "Top-level violation counts represent distinct violated "
                "constraints, avoiding duplication when one constraint "
                "affects multiple positions."
            ),
            (
                "Explanations are descriptive. They do not predict returns, "
                "rank positions, or instruct the user to buy or sell."
            ),
        ]

        if outside_range_count > 0:
            notes.append(
                (
                    f"{outside_range_count} position(s) are currently "
                    "outside their reference allocation ranges."
                ),
            )

        if violation_count > 0:
            notes.append(
                (
                    f"{violation_count} distinct configured risk "
                    "constraint violation(s) are currently present."
                ),
            )

        if ranges.quality == "partial" or constraints.quality == "partial":
            notes.append(
                (
                    "Some currency groups have incomplete quote coverage; "
                    "their explanations are therefore marked unavailable."
                ),
            )

        return PortfolioAllocationExplanations(
            portfolio=ranges.portfolio,
            assessed_at=ranges.assessed_at,
            maximum_quote_age_seconds=ranges.maximum_quote_age_seconds,
            range_tolerance=ranges.range_tolerance,
            maximum_position_weight=constraints.maximum_position_weight,
            maximum_asset_class_weight=constraints.maximum_asset_class_weight,
            quality=quality,
            explanation_count=explanation_count,
            outside_range_count=outside_range_count,
            violation_count=violation_count,
            currencies=tuple(currency_results),
            items=tuple(items),
            methodology=self._methodology(),
            notes=tuple(notes),
        )

    @staticmethod
    def _determine_status(
        range_item,
    ):
        """Determine current position state relative to its allocation range."""

        if range_item.quality != "current" or range_item.current_weight is None:
            return "unavailable"

        if range_item.current_weight < range_item.minimum_weight:
            return "below_minimum"

        if range_item.current_weight > range_item.maximum_weight:
            return "above_maximum"

        return "within_range"

    @staticmethod
    def _build_position_explanation(
        *,
        range_item,
        status,
        violations,
    ) -> str:
        """Build a descriptive explanation for one position."""

        if status == "unavailable":
            explanation = (
                "The current allocation cannot be fully explained because "
                "an accepted current quote is unavailable for this currency "
                "group."
            )
        elif status == "below_minimum":
            explanation = (
                f"Current weight is {range_item.current_weight} while the "
                f"reference allocation range begins at "
                f"{range_item.minimum_weight}, below the "
                f"{range_item.target_weight} target."
            )
        elif status == "above_maximum":
            explanation = (
                f"Current weight is {range_item.current_weight} while the "
                f"reference allocation range ends at "
                f"{range_item.maximum_weight}, above the "
                f"{range_item.target_weight} target."
            )
        else:
            explanation = (
                f"Current weight is {range_item.current_weight}, within the "
                f"reference allocation range of "
                f"{range_item.minimum_weight} to "
                f"{range_item.maximum_weight} around the "
                f"{range_item.target_weight} target."
            )

        if violations:
            violation_text = "; ".join(
                (
                    f"{constraint.kind} is violated because observed "
                    f"weight {constraint.observed_weight} exceeds the "
                    f"configured limit {constraint.limit}."
                )
                for constraint in violations
            )

            explanation = f"{explanation} {violation_text}"

        return explanation

    @staticmethod
    def _build_currency_explanation(
        *,
        currency: str,
        currency_items,
        outside_range_count: int,
        violation_count: int,
    ) -> str:
        """Build a summary explanation for one currency."""

        unavailable_count = sum(
            item.quality == "unavailable" for item in currency_items
        )

        if unavailable_count > 0:
            return (
                f"{currency} contains {len(currency_items)} position(s), "
                f"but {unavailable_count} cannot be fully explained because "
                "accepted current quote data is incomplete."
            )

        if outside_range_count == 0 and violation_count == 0:
            return (
                f"All {len(currency_items)} {currency} position(s) are "
                "within their reference allocation ranges and no configured "
                "risk constraints are violated."
            )

        return (
            f"{outside_range_count} of {len(currency_items)} {currency} "
            "position(s) are outside their reference allocation ranges, "
            f"with {violation_count} distinct configured risk constraint "
            "violation(s)."
        )

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
    ) -> None:
        """Require a timezone-aware assessment timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "assessed_at must be timezone-aware",
            )

    @staticmethod
    def _methodology() -> str:
        """Describe the allocation explanation methodology."""

        return (
            "Allocation explanations are derived from the existing "
            "equal-weight reference sizing, allocation ranges, and explicit "
            "position and asset-class risk constraints. Current position "
            "weights are classified as below minimum, within range, above "
            "maximum, or unavailable. Configured constraint violations are "
            "attached to the affected position or currency-specific asset "
            "class. Top-level violation counts use distinct persisted "
            "constraint identifiers so shared asset-class violations are not "
            "counted multiple times. No predictive model, return forecast, "
            "ranking, or trade instruction is generated."
        )
