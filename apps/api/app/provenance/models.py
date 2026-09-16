from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisStage(StrEnum):
    """Stage that produced an analytical result."""

    NEWS_INTELLIGENCE = "news_intelligence"
    EVENT_INTELLIGENCE = "event_intelligence"
    COMPANY_IMPACT = "company_impact"
    MARKET_IMPACT = "market_impact"
    SIGNAL_INTELLIGENCE = "signal_intelligence"
    RISK_CONFIDENCE = "risk_confidence"
    RECOMMENDATION = "recommendation"
    BACKTESTING = "backtesting"


class EvidenceReference(BaseModel):
    """Reference to source evidence used by an analytical result."""

    model_config = ConfigDict(frozen=True)

    article_id: UUID
    source_name: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1)
    published_at: datetime | None = None
    discovered_at: datetime
    retrieved_at: datetime
    relevance_note: str = Field(min_length=1)


class ProvenanceRecord(BaseModel):
    """Traceability metadata for a MarketThread analytical result."""

    model_config = ConfigDict(frozen=True)

    result_id: UUID
    stage: AnalysisStage
    created_at: datetime
    ruleset_version: str = Field(min_length=1, max_length=64)
    evidence: tuple[EvidenceReference, ...] = ()
    input_ids: tuple[UUID, ...] = ()
    assumptions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
