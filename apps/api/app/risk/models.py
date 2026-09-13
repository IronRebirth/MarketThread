from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceLevel(StrEnum):
    """Qualitative level of evidence confidence."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class RiskLevel(StrEnum):
    """Qualitative level of interpretation risk."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactor(StrEnum):
    """Factor contributing to interpretation risk."""

    LIMITED_EVIDENCE = "limited_evidence"
    INDIRECT_EXPOSURE = "indirect_exposure"
    HORIZON_UNCERTAINTY = "horizon_uncertainty"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    EVENT_UNCERTAINTY = "event_uncertainty"
    MODEL_LIMITATION = "model_limitation"


class ConfidenceAssessment(BaseModel):
    """Explainable assessment of evidence confidence."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    supporting_factors: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)


class RiskAssessment(BaseModel):
    """Explainable assessment of interpretation risk."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    level: RiskLevel
    factors: tuple[RiskFactor, ...] = ()
    rationale: str = Field(min_length=1)


class RiskConfidenceAssessment(BaseModel):
    """Combined risk and confidence assessment for a market signal."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    confidence: ConfidenceAssessment
    risk: RiskAssessment
    evidence_article_ids: tuple[UUID, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
