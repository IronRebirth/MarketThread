from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recommendation_provenance import (
    RecommendationProvenanceRecord,
)

from .provenance import RecommendationProvenance


class RecommendationProvenancePersistenceError(Exception):
    """Base error for recommendation provenance persistence."""


class RecommendationProvenanceNotFoundError(
    RecommendationProvenancePersistenceError,
):
    """Raised when recommendation provenance does not exist."""


class RecommendationProvenancePersistenceService:
    """Persist immutable recommendation provenance snapshots."""

    async def create(
        self,
        session: AsyncSession,
        *,
        provenance: RecommendationProvenance,
        created_at: datetime,
        provenance_id: UUID | None = None,
    ) -> RecommendationProvenanceRecord:
        """Persist provenance idempotently."""

        existing = await self.get_by_recommendation_id(
            session,
            provenance.recommendation_id,
        )

        if existing is not None:
            return existing

        record = RecommendationProvenanceRecord(
            id=provenance_id or uuid4(),
            recommendation_id=provenance.recommendation_id,
            signal_id=provenance.signal_id,
            market_impact_id=provenance.market_impact_id,
            event_id=provenance.event_id,
            created_at=created_at,
            ruleset_version=provenance.ruleset_version,
            input_ids=[str(input_id) for input_id in provenance.input_ids],
            evidence_article_ids=[
                str(article_id) for article_id in provenance.evidence_article_ids
            ],
            assumptions=list(provenance.assumptions),
            invalidation_conditions=list(
                provenance.invalidation_conditions,
            ),
        )

        session.add(record)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

            existing = await self.get_by_recommendation_id(
                session,
                provenance.recommendation_id,
            )

            if existing is None:
                raise

            return existing

        await session.refresh(record)

        return record

    async def get(
        self,
        session: AsyncSession,
        provenance_id: UUID,
    ) -> RecommendationProvenanceRecord:
        """Retrieve one recommendation provenance record."""

        record = await session.get(
            RecommendationProvenanceRecord,
            provenance_id,
        )

        if record is None:
            raise RecommendationProvenanceNotFoundError(
                f"Recommendation provenance {provenance_id} was not found.",
            )

        return record

    async def get_by_recommendation_id(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
    ) -> RecommendationProvenanceRecord | None:
        """Retrieve provenance associated with one recommendation."""

        return await session.scalar(
            select(RecommendationProvenanceRecord).where(
                RecommendationProvenanceRecord.recommendation_id == recommendation_id,
            ),
        )

    @staticmethod
    def to_domain(
        record: RecommendationProvenanceRecord,
    ) -> RecommendationProvenance:
        """Convert a persisted record into its domain representation."""

        return RecommendationProvenance(
            recommendation_id=record.recommendation_id,
            signal_id=record.signal_id,
            market_impact_id=record.market_impact_id,
            event_id=record.event_id,
            created_at=record.created_at,
            ruleset_version=record.ruleset_version,
            input_ids=tuple(UUID(input_id) for input_id in record.input_ids),
            evidence_article_ids=tuple(
                UUID(article_id) for article_id in record.evidence_article_ids
            ),
            assumptions=tuple(record.assumptions),
            invalidation_conditions=tuple(
                record.invalidation_conditions,
            ),
        )
