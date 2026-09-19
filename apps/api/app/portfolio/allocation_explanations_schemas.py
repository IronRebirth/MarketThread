from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.allocation_explanations_models import (
    AllocationExplanationItemQuality,
    AllocationExplanationQuality,
    AllocationExplanationStatus,
)
from app.portfolio.models import PortfolioPosition
from app.portfolio.risk_constraints_models import RiskConstraintKind
from app.portfolio.schemas import PortfolioResponse


class PortfolioAllocationExplanationItemResponse(BaseModel):
    """API representation of one allocation explanation."""

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


class PortfolioAllocationExplanationCurrencyResponse(BaseModel):
    """API representation of one currency's allocation explanation."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: Literal["current", "unavailable"]

    explanation_count: int = Field(ge=0)
    outside_range_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)

    explanation: str = Field(min_length=1)


class PortfolioAllocationExplanationsResponse(BaseModel):
    """API representation of portfolio allocation explanations."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    range_tolerance: Decimal = Field(gt=0, le=1)

    maximum_position_weight: Decimal = Field(gt=0, le=1)
    maximum_asset_class_weight: Decimal = Field(gt=0, le=1)

    quality: AllocationExplanationQuality

    explanation_count: int = Field(ge=0)
    outside_range_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)

    currencies: tuple[PortfolioAllocationExplanationCurrencyResponse, ...]
    items: tuple[PortfolioAllocationExplanationItemResponse, ...]

    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
