from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImpactType(StrEnum):
    """Relationship between a market event and a company."""

    DIRECT = "direct"
    INDIRECT = "indirect"


class CompanyImpactDirection(StrEnum):
    """Potential directional effect on a company."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNCERTAIN = "uncertain"


class CompanyImpact(BaseModel):
    """Structured impact of a market event on a company."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = Field(default=None, max_length=32)
    impact_type: ImpactType
    direction: CompanyImpactDirection
    mechanism: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_article_ids: tuple[UUID, ...] = ()
    rationale: str = Field(min_length=1)
