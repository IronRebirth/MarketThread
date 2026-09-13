from datetime import UTC, datetime
from uuid import UUID

from app.provenance.models import (
    AnalysisStage,
    EvidenceReference,
    ProvenanceRecord,
)


class ProvenanceService:
    """Build traceability records for MarketThread analytical results."""

    def create_record(
        self,
        result_id: UUID,
        stage: AnalysisStage,
        input_ids: tuple[UUID, ...],
        evidence: tuple[EvidenceReference, ...],
        assumptions: tuple[str, ...],
        invalidation_conditions: tuple[str, ...],
        ruleset_version: str = "1.0.0",
    ) -> ProvenanceRecord:
        """Create an immutable provenance record."""

        return ProvenanceRecord(
            result_id=result_id,
            stage=stage,
            created_at=datetime.now(UTC),
            ruleset_version=ruleset_version,
            evidence=evidence,
            input_ids=input_ids,
            assumptions=assumptions,
            invalidation_conditions=invalidation_conditions,
        )
