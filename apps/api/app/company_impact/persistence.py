from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord

from .models import CompanyImpact, CompanyImpactDirection, ImpactType


class CompanyImpactPersistenceError(Exception):
    """Base error for company impact persistence."""


class CompanyImpactNotFoundError(CompanyImpactPersistenceError):
    """Raised when a persisted company impact does not exist."""


class CompanyImpactPersistenceService:
    """Persist deterministic company impact snapshots."""

    async def persist(
        self,
        session: AsyncSession,
        impact: CompanyImpact,
    ) -> CompanyImpact:
        """Persist one company impact idempotently."""

        existing = await session.scalar(
            select(CompanyImpactRecord).where(
                CompanyImpactRecord.event_id == impact.event_id,
                CompanyImpactRecord.company_name == impact.company_name,
                CompanyImpactRecord.impact_type == impact.impact_type.value,
            ),
        )

        if existing is not None:
            return self._to_domain(existing)

        record = CompanyImpactRecord(
            event_id=impact.event_id,
            company_name=impact.company_name,
            ticker=impact.ticker,
            impact_type=impact.impact_type.value,
            direction=impact.direction.value,
            mechanism=impact.mechanism,
            confidence=impact.confidence,
            evidence_article_ids=[
                str(article_id) for article_id in impact.evidence_article_ids
            ],
            rationale=impact.rationale,
        )

        session.add(record)

        await session.commit()
        await session.refresh(record)

        return self._to_domain(record)

    async def persist_many(
        self,
        session: AsyncSession,
        impacts: Sequence[CompanyImpact],
    ) -> tuple[CompanyImpact, ...]:
        """Persist multiple company impacts idempotently."""

        persisted: list[CompanyImpact] = []

        for impact in impacts:
            persisted.append(await self.persist(session, impact))

        return tuple(persisted)

    async def get(
        self,
        session: AsyncSession,
        impact_id: UUID,
    ) -> CompanyImpact:
        """Retrieve one persisted company impact."""

        record = await session.get(
            CompanyImpactRecord,
            impact_id,
        )

        if record is None:
            raise CompanyImpactNotFoundError(
                f"Company impact {impact_id} was not found.",
            )

        return self._to_domain(record)

    async def list(
        self,
        session: AsyncSession,
        *,
        event_id: UUID | None = None,
        company_name: str | None = None,
        ticker: str | None = None,
        impact_type: str | None = None,
        direction: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
    ) -> tuple[CompanyImpact, ...]:
        """List persisted company impacts with optional event filters."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if start_at is not None and end_at is not None and start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        statement = select(CompanyImpactRecord).join(
            EventRecord,
            EventRecord.id == CompanyImpactRecord.event_id,
        )

        if event_id is not None:
            statement = statement.where(
                CompanyImpactRecord.event_id == event_id,
            )

        if company_name is not None:
            statement = statement.where(
                CompanyImpactRecord.company_name == company_name,
            )

        if ticker is not None:
            statement = statement.where(
                CompanyImpactRecord.ticker == ticker,
            )

        if impact_type is not None:
            statement = statement.where(
                CompanyImpactRecord.impact_type == impact_type,
            )

        if direction is not None:
            statement = statement.where(
                CompanyImpactRecord.direction == direction,
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
            CompanyImpactRecord.company_name.asc(),
        ).limit(limit)

        result = await session.execute(statement)

        records: Sequence[CompanyImpactRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_domain(record: CompanyImpactRecord) -> CompanyImpact:
        """Convert a persisted record into its domain representation."""

        return CompanyImpact(
            event_id=record.event_id,
            company_name=record.company_name,
            ticker=record.ticker,
            impact_type=ImpactType(record.impact_type),
            direction=CompanyImpactDirection(record.direction),
            mechanism=record.mechanism,
            confidence=record.confidence,
            evidence_article_ids=tuple(
                UUID(article_id) for article_id in record.evidence_article_ids
            ),
            rationale=record.rationale,
        )
