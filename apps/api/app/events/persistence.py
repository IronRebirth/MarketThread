from collections.abc import Sequence
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import EventRecord

from .models import MarketEvent


class EventPersistenceError(Exception):
    """Base error for event persistence."""


class EventNotFoundError(EventPersistenceError):
    """Raised when a persisted event does not exist."""


class EventPersistenceService:
    """Persist normalized market-event snapshots."""

    async def persist(
        self,
        session: AsyncSession,
        event: MarketEvent,
    ) -> MarketEvent:
        """Persist an event idempotently using its source and classification."""

        deduplication_key = _build_deduplication_key(event)

        existing = await session.scalar(
            select(EventRecord).where(
                EventRecord.deduplication_key == deduplication_key,
            ),
        )

        if existing is not None:
            return self._to_domain(existing)

        record = EventRecord(
            id=event.event_id,
            deduplication_key=deduplication_key,
            event_type=event.event_type.value,
            title=event.title,
            summary=event.summary,
            catalyst=event.catalyst.value,
            market_relevance=event.market_relevance.value,
            impact_direction=event.impact_direction.value,
            affected_entities=list(event.affected_entities),
            affected_sectors=list(event.affected_sectors),
            source_article_ids=[
                str(article_id) for article_id in event.source_article_ids
            ],
            first_seen_at=event.first_seen_at,
            last_seen_at=event.last_seen_at,
            confidence=event.confidence,
        )

        session.add(record)

        await session.commit()
        await session.refresh(record)

        return self._to_domain(record)

    async def get(
        self,
        session: AsyncSession,
        event_id: UUID,
    ) -> MarketEvent:
        """Retrieve one persisted market event."""

        record = await session.get(
            EventRecord,
            event_id,
        )

        if record is None:
            raise EventNotFoundError(
                f"Event {event_id} was not found.",
            )

        return self._to_domain(record)

    async def list(
        self,
        session: AsyncSession,
        *,
        event_type: str | None = None,
        catalyst: str | None = None,
        market_relevance: str | None = None,
        impact_direction: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 50,
    ) -> tuple[MarketEvent, ...]:
        """List persisted events with optional metadata filters."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if start_at is not None and end_at is not None and start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        statement = select(EventRecord)

        if event_type is not None:
            statement = statement.where(
                EventRecord.event_type == event_type,
            )

        if catalyst is not None:
            statement = statement.where(
                EventRecord.catalyst == catalyst,
            )

        if market_relevance is not None:
            statement = statement.where(
                EventRecord.market_relevance == market_relevance,
            )

        if impact_direction is not None:
            statement = statement.where(
                EventRecord.impact_direction == impact_direction,
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
            EventRecord.last_seen_at.desc(),
        ).limit(limit)

        result = await session.execute(statement)

        records: Sequence[EventRecord] = result.scalars().all()

        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_domain(record: EventRecord) -> MarketEvent:
        """Convert a persisted event record into its domain representation."""

        return MarketEvent(
            event_id=record.id,
            event_type=record.event_type,
            title=record.title,
            summary=record.summary,
            catalyst=record.catalyst,
            market_relevance=record.market_relevance,
            impact_direction=record.impact_direction,
            affected_entities=tuple(record.affected_entities),
            affected_sectors=tuple(record.affected_sectors),
            source_article_ids=tuple(
                UUID(article_id) for article_id in record.source_article_ids
            ),
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            confidence=record.confidence,
        )


def _build_deduplication_key(event: MarketEvent) -> str:
    """Build a stable key for an identical source/classification snapshot."""

    source_ids = ",".join(
        sorted(str(article_id) for article_id in event.source_article_ids),
    )

    raw_key = f"{source_ids}|{event.event_type.value}|{event.catalyst.value}"

    return sha256(raw_key.encode()).hexdigest()
