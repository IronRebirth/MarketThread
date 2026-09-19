from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.portfolio.cash_flow_models import PortfolioCashFlow


class PortfolioCashFlowCreateRequest(BaseModel):
    """Request to append an external cash-flow event."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["deposit", "withdrawal"]
    currency: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0)
    effective_at: datetime

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """Normalize currency codes to uppercase ISO-style codes."""

        normalized = value.strip().upper()

        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError(
                "Currency must be a three-letter alphabetic code.",
            )

        return normalized

    @field_validator("effective_at")
    @classmethod
    def validate_effective_at(cls, value: datetime) -> datetime:
        """Require an unambiguous timezone-aware effective timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must be timezone-aware")

        return value.astimezone(UTC)


class PortfolioCashFlowResponse(PortfolioCashFlow):
    """API representation of an immutable portfolio cash-flow event."""

    model_config = ConfigDict(from_attributes=True)
