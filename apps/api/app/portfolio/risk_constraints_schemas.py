from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import PortfolioPosition
from app.portfolio.risk_constraints_models import (
    RiskConstraintKind,
    RiskConstraintScope,
    RiskConstraintsQuality,
    RiskConstraintStatus,
)
from app.portfolio.schemas import PortfolioResponse


class PortfolioRiskConstraintResponse(BaseModel):
    """API representation of one evaluated risk constraint."""

    model_config = ConfigDict(frozen=True)

    constraint_id: UUID
    kind: RiskConstraintKind
    scope: RiskConstraintScope
    currency: str = Field(min_length=3, max_length=3)

    subject: str = Field(min_length=1, max_length=255)
    position: PortfolioPosition | None
    asset_class: str | None

    observed_weight: Decimal | None
    limit: Decimal = Field(gt=0, le=1)
    headroom: Decimal | None

    status: RiskConstraintStatus
    rationale: str = Field(min_length=1)


class PortfolioRiskConstraintCurrencyResponse(BaseModel):
    """API representation of one currency's risk-constraint summary."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: Literal["current", "unavailable"]

    current_market_value: Decimal | None
    constraint_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)


class PortfolioRiskConstraintsResponse(BaseModel):
    """API representation of portfolio risk constraints."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float

    maximum_position_weight: Decimal = Field(gt=0, le=1)
    maximum_asset_class_weight: Decimal = Field(gt=0, le=1)

    quality: RiskConstraintsQuality

    evaluated_constraint_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)

    currencies: tuple[PortfolioRiskConstraintCurrencyResponse, ...]
    constraints: tuple[PortfolioRiskConstraintResponse, ...]

    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
