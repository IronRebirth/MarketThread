from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio

HistoryEventType = Literal[
    "created",
    "updated",
    "deleted",
    "backfilled",
]

HistoricalStateQuality = Literal[
    "complete",
    "empty",
]


class PortfolioHistoricalPosition(BaseModel):
    """A position reconstructed from the historical position event stream."""

    model_config = ConfigDict(frozen=True)

    history_sequence_id: int = Field(gt=0)
    portfolio_id: UUID
    instrument_id: UUID
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(ge=0)
    event_type: HistoryEventType
    effective_at: datetime

    symbol: str
    name: str
    exchange: str
    asset_class: str
    currency: str
    is_active: bool


class PortfolioHistoricalState(BaseModel):
    """Portfolio positions that existed at a historical point in time."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    as_of: datetime
    position_count: int = Field(ge=0)
    quality: HistoricalStateQuality
    methodology: str = Field(min_length=1)
    positions: tuple[PortfolioHistoricalPosition, ...]
