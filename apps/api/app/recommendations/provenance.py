from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecommendationProvenance(BaseModel):
    """Immutable provenance snapshot for a persisted recommendation."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID
    signal_id: UUID
    market_impact_id: UUID
    event_id: UUID
    created_at: datetime
    ruleset_version: str = Field(min_length=1, max_length=64)
    input_ids: tuple[UUID, ...] = ()
    evidence_article_ids: tuple[UUID, ...] = ()
    assumptions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
