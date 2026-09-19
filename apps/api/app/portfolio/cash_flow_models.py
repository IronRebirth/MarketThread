from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PortfolioCashFlowEventType = Literal[
    "deposit",
    "withdrawal",
]


class PortfolioCashFlow(BaseModel):
    """Normalized immutable external cash-flow event."""

    model_config = ConfigDict(frozen=True)

    sequence_id: int = Field(gt=0)
    cash_flow_id: UUID
    portfolio_id: UUID
    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0)
    event_type: PortfolioCashFlowEventType
    effective_at: datetime
    recorded_at: datetime
