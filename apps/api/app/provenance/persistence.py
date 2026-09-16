from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provenance import BacktestProvenance

from .models import EvidenceReference, ProvenanceRecord


class ProvenancePersistenceError(Exception):
    """Base error for provenance persistence operations."""


class ProvenanceAlreadyExistsError(ProvenancePersistenceError):
    """Raised when provenance for a result already exists."""


class ProvenanceNotFoundError(ProvenancePersistenceError):
    """Raised when provenance for a result does not exist."""


class ProvenancePersistenceService:
    """Persist and restore immutable provenance records."""

    async def save(
        self,
        session: AsyncSession,
        record: ProvenanceRecord,
    ) -> BacktestProvenance:
        result = await session.execute(
            select(BacktestProvenance).where(
                BacktestProvenance.backtest_id == record.result_id,
            ),
        )

        existing = result.scalar_one_or_none()

        if existing is not None:
            raise ProvenanceAlreadyExistsError(
                f"Provenance for result {record.result_id} already exists.",
            )

        persisted = BacktestProvenance(
            id=uuid4(),
            backtest_id=record.result_id,
            stage=record.stage.value,
            ruleset_version=record.ruleset_version,
            input_ids=[str(input_id) for input_id in record.input_ids],
            evidence=[evidence.model_dump(mode="json") for evidence in record.evidence],
            assumptions=list(record.assumptions),
            invalidation_conditions=list(record.invalidation_conditions),
            created_at=record.created_at,
        )

        session.add(persisted)

        await session.commit()
        await session.refresh(persisted)

        return persisted

    async def get(
        self,
        session: AsyncSession,
        result_id: UUID,
    ) -> ProvenanceRecord:
        result = await session.execute(
            select(BacktestProvenance).where(
                BacktestProvenance.backtest_id == result_id,
            ),
        )

        persisted = result.scalar_one_or_none()

        if persisted is None:
            raise ProvenanceNotFoundError(
                f"Provenance for result {result_id} was not found.",
            )

        return ProvenanceRecord(
            result_id=persisted.backtest_id,
            stage=persisted.stage,
            created_at=persisted.created_at,
            ruleset_version=persisted.ruleset_version,
            evidence=tuple(
                self._evidence_from_payload(item) for item in persisted.evidence
            ),
            input_ids=tuple(UUID(input_id) for input_id in persisted.input_ids),
            assumptions=tuple(persisted.assumptions),
            invalidation_conditions=tuple(
                persisted.invalidation_conditions,
            ),
        )

    @staticmethod
    def _evidence_from_payload(
        payload: dict,
    ) -> EvidenceReference:
        return EvidenceReference.model_validate(payload)
