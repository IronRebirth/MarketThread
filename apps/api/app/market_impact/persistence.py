from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import EventRecord
from app.db.models.market_impact import MarketImpactRecord

from .models import ImpactFactor, MarketImpact, TimeHorizon


class MarketImpactPersistenceError(Exception):
    """Base error for market impact persistence."""


class MarketImpactNotFoundError(MarketImpactPersistenceError):
    """Raised when a persisted market impact does not exist."""


class MarketImpactPersistenceService:
    """Persist structured market-impact snapshots."""

    async def persist(
        self,
        session: AsyncSession,
        market_impact: MarketImpact,
        company_impact_id: UUID,
    ) -> MarketImpact:
        """Persist one market impact idempotently."""

        existing = await session.scalar(
            select(MarketImpactRecord).where(
                MarketImpactRecord.company_impact_id == company_impact_id,
            ),
        )

        if existing is not None:
            return self._to_domain(existing)

        record = MarketImpactRecord(
            event_id=market_impact.event_id,
            company_impact_id=company_impact_id,
            company_name=market_impact.company_name,
            ticker=market_impact.ticker,
            impact_type=market_impact.impact_type.value,
            direction=market_impact.direction.value,
            factor=market_impact.factor.value,
            time_horizon=market_impact.time_horizon.value,
            confidence=market_impact.confidence,
            evidence_article_ids=[
                str(article_id) for article_id in market_impact.evidence_article_ids
            ],
            rationale=market_impact.rationale,
        )

        session.add(record)

        await session.commit()
        await session.refresh(record)

        return self._to_domain(record)

    async def get(
        self,
        session: AsyncSession,
        market_impact_id: UUID,
    ) -> MarketImpact:
        """Retrieve one persisted market impact."""

        record = await session.get(
            MarketImpactRecord,
            market_impact_id,
        )

        if record is None:
            raise MarketImpactNotFoundError(
                f"Market impact {market_impact_id} was not found.",
            )

        return self._to_domain(record)

    async def list(
        self,
        session: AsyncSession,
        *,
        event_id: UUID | None = None,
        company_name: str | None = None,
        impact_type: str | None = None,
        direction: str | None = None,
        factor: str | None = None,
        time_horizon: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> tuple[tuple[UUID, MarketImpact], ...]:
        """List persisted market impacts with optional filters."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if start_at is not None and end_at is not None and start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        statement = select(MarketImpactRecord).join(
            EventRecord,
            EventRecord.id == MarketImpactRecord.event_id,
        )

        if event_id is not None:
            statement = statement.where(
                MarketImpactRecord.event_id == event_id,
            )

        if company_name is not None:
            statement = statement.where(
                MarketImpactRecord.company_name == company_name,
            )

        if impact_type is not None:
            statement = statement.where(
                MarketImpactRecord.impact_type == impact_type,
            )

        if direction is not None:
            statement = statement.where(
                MarketImpactRecord.direction == direction,
            )

        if factor is not None:
            statement = statement.where(
                MarketImpactRecord.factor == factor,
            )

        if time_horizon is not None:
            statement = statement.where(
                MarketImpactRecord.time_horizon == time_horizon,
            )

        if start_at is not None:
            statement = statement.where(
                EventRecord.first_seen_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                EventRecord.first_seen_at < end_at,
            )

        statement = statement.order_by(
            EventRecord.first_seen_at.desc(),
            MarketImpactRecord.company_name.asc(),
        ).limit(limit)

        result = await session.execute(statement)

        records: Sequence[MarketImpactRecord] = result.scalars().all()

        return tuple(
            (
                record.id,
                self._to_domain(record),
            )
            for record in records
        )

    @staticmethod
    def _to_domain(record: MarketImpactRecord) -> MarketImpact:
        """Convert a persisted record into its domain representation."""

        return MarketImpact(
            event_id=record.event_id,
            company_name=record.company_name,
            ticker=record.ticker,
            impact_type=record.impact_type,
            direction=record.direction,
            factor=ImpactFactor(record.factor),
            time_horizon=TimeHorizon(record.time_horizon),
            confidence=record.confidence,
            evidence_article_ids=tuple(
                UUID(article_id) for article_id in record.evidence_article_ids
            ),
            rationale=record.rationale,
        )
