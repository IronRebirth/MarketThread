from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio, PortfolioPosition
from app.portfolio.risk_constraints_models import RiskConstraintKind

AllocationExplanationQuality = Literal[
    "sufficient",
    "partial",
    "none",
    "empty",
]

AllocationExplanationStatus = Literal[
    "within_range",
    "below_minimum",
    "above_maximum",
    "unavailable",
]

AllocationExplanationItemQuality = Literal[
    "current",
    "unavailable",
]


class PortfolioAllocationExplanationItem(BaseModel):
    """Explain the current allocation state of one portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: AllocationExplanationItemQuality
    status: AllocationExplanationStatus

    current_market_value: Decimal | None
    current_weight: Decimal | None

    minimum_weight: Decimal = Field(ge=0, le=1)
    target_weight: Decimal = Field(gt=0, le=1)
    maximum_weight: Decimal = Field(gt=0, le=1)

    constraint_violation_count: int = Field(ge=0)
    violated_constraints: tuple[RiskConstraintKind, ...]

    explanation: str = Field(min_length=1)
    notes: tuple[str, ...]


class PortfolioAllocationExplanationCurrency(BaseModel):
    """Explain allocation state for one portfolio currency."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: Literal["current", "unavailable"]

    explanation_count: int = Field(ge=0)
    outside_range_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)

    explanation: str = Field(min_length=1)


class PortfolioAllocationExplanations(BaseModel):
    """Quality-aware explanations for portfolio allocation state."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    range_tolerance: Decimal = Field(gt=0, le=1)

    maximum_position_weight: Decimal = Field(gt=0, le=1)
    maximum_asset_class_weight: Decimal = Field(gt=0, le=1)

    quality: AllocationExplanationQuality

    explanation_count: int = Field(ge=0)
    outside_range_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)

    currencies: tuple[PortfolioAllocationExplanationCurrency, ...]
    items: tuple[PortfolioAllocationExplanationItem, ...]

    methodology: str
    notes: tuple[str, ...]
