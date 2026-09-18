from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Portfolio(BaseModel):
    """Normalized user-owned investment portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    name: str = Field(min_length=1, max_length=100)
    created_at: datetime
    updated_at: datetime
    position_count: int = Field(ge=0)


class PortfolioPosition(BaseModel):
    """Current position held inside a user-owned portfolio."""

    model_config = ConfigDict(frozen=True)

    position_id: UUID
    portfolio_id: UUID
    instrument_id: UUID
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    exchange: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=3, max_length=3)
    is_active: bool


class PortfolioDetail(Portfolio):
    """Portfolio with its persisted current positions."""

    positions: tuple[PortfolioPosition, ...] = ()
