from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recommendation import RecommendationRecord

from .models import Recommendation


class RecommendationPersistenceError(Exception):
    """Base error for recommendation persistence."""


class RecommendationNotFoundError(RecommendationPersistenceError):
    """Raised when a persisted recommendation does not exist."""


class RecommendationPersistenceService:
    """Persist immutable recommendation snapshots."""

    async def create(
        self,
        session: AsyncSession,
        *,
        recommendation: Recommendation,
        signal_id: UUID,
        created_at: datetime,
        recommendation_id: UUID | None = None,
    ) -> RecommendationRecord:
        """Persist one recommendation idempotently."""

        existing = await self.get_by_signal_id(
            session,
            signal_id,
        )

        if existing is not None:
            return existing

        record = RecommendationRecord(
            id=recommendation_id or uuid4(),
            signal_id=signal_id,
            event_id=recommendation.event_id,
            company_name=recommendation.company_name,
            ticker=recommendation.ticker,
            created_at=created_at,
            state=recommendation.state.value,
            signal_direction=recommendation.signal_direction,
            confidence_score=recommendation.confidence_score,
            risk_score=recommendation.risk_score,
            confidence_level=recommendation.confidence_level,
            risk_level=recommendation.risk_level,
            time_horizon=recommendation.time_horizon,
            supporting_factors=list(recommendation.supporting_factors),
            contradicting_factors=list(recommendation.contradicting_factors),
            assumptions=list(recommendation.assumptions),
            invalidation_conditions=list(
                recommendation.invalidation_conditions,
            ),
            evidence_article_ids=[
                str(article_id) for article_id in recommendation.evidence_article_ids
            ],
            rationale=recommendation.rationale,
        )

        session.add(record)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

            existing = await self.get_by_signal_id(
                session,
                signal_id,
            )

            if existing is None:
                raise

            return existing

        await session.refresh(record)

        return record

    async def get(
        self,
        session: AsyncSession,
        recommendation_id: UUID,
    ) -> RecommendationRecord:
        """Retrieve one persisted recommendation."""

        record = await session.get(
            RecommendationRecord,
            recommendation_id,
        )

        if record is None:
            raise RecommendationNotFoundError(
                f"Recommendation {recommendation_id} was not found.",
            )

        return record

    async def get_by_signal_id(
        self,
        session: AsyncSession,
        signal_id: UUID,
    ) -> RecommendationRecord | None:
        """Retrieve the recommendation generated for one signal."""

        return await session.scalar(
            select(RecommendationRecord).where(
                RecommendationRecord.signal_id == signal_id,
            ),
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        signal_id: UUID | None = None,
        company_name: str | None = None,
        ticker: str | None = None,
        state: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> tuple[RecommendationRecord, ...]:
        """List persisted recommendations with optional filters."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if start_at is not None and end_at is not None and start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        statement = select(RecommendationRecord)

        if signal_id is not None:
            statement = statement.where(
                RecommendationRecord.signal_id == signal_id,
            )

        if company_name is not None:
            statement = statement.where(
                RecommendationRecord.company_name == company_name,
            )

        if ticker is not None:
            statement = statement.where(
                RecommendationRecord.ticker == ticker.upper(),
            )

        if state is not None:
            statement = statement.where(
                RecommendationRecord.state == state,
            )

        if start_at is not None:
            statement = statement.where(
                RecommendationRecord.created_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                RecommendationRecord.created_at < end_at,
            )

        statement = statement.order_by(
            RecommendationRecord.created_at.desc(),
        ).limit(limit)

        result = await session.execute(statement)

        return tuple(result.scalars().all())
