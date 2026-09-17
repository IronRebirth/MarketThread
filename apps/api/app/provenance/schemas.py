from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .models import AnalysisStage, ProvenanceRecord


class ProvenanceEvidenceResponse(BaseModel):
    """API representation of source evidence used by an analysis."""

    article_id: UUID
    source_name: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1)
    published_at: datetime | None = None
    discovered_at: datetime
    retrieved_at: datetime
    relevance_note: str = Field(min_length=1)


class BacktestProvenanceResponse(BaseModel):
    """API representation of persisted backtest provenance."""

    result_id: UUID
    stage: AnalysisStage
    created_at: datetime
    ruleset_version: str = Field(min_length=1, max_length=64)
    evidence: tuple[ProvenanceEvidenceResponse, ...] = ()
    input_ids: tuple[UUID, ...] = ()
    assumptions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()


def to_backtest_response(
    record: ProvenanceRecord,
) -> BacktestProvenanceResponse:
    """Convert the provenance domain record into its API representation."""

    return BacktestProvenanceResponse(
        result_id=record.result_id,
        stage=record.stage,
        created_at=record.created_at,
        ruleset_version=record.ruleset_version,
        evidence=tuple(
            ProvenanceEvidenceResponse.model_validate(item.model_dump())
            for item in record.evidence
        ),
        input_ids=record.input_ids,
        assumptions=record.assumptions,
        invalidation_conditions=record.invalidation_conditions,
    )
