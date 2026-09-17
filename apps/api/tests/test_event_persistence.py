from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.models.event import EventRecord
from app.events.models import MarketEvent
from app.events.persistence import (
    EventNotFoundError,
    EventPersistenceService,
)
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance

persistence_service = EventPersistenceService()


def build_event(
    *,
    source_article_id=None,
    event_type=EventType.MONETARY_POLICY,
    catalyst=EventCatalyst.RATE_CUT,
    first_seen_at: datetime | None = None,
) -> MarketEvent:
    """Build a representative market event."""

    article_id = source_article_id or uuid4()
    timestamp = first_seen_at or datetime.now(UTC)

    return MarketEvent(
        event_id=uuid4(),
        event_type=event_type,
        title="Central bank approves interest rate cut",
        summary="Policy makers reduced interest rates.",
        catalyst=catalyst,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.POSITIVE,
        affected_entities=("Example Company",),
        affected_sectors=("Technology",),
        source_article_ids=(article_id,),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


async def cleanup_events(db_session, event_ids: list) -> None:
    """Remove only the event records created by a test."""

    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id.in_(event_ids),
        ),
    )
    await db_session.commit()


async def test_persist_get_and_list_event(db_session) -> None:
    """Persist, retrieve, and filter a market event."""

    event = build_event()

    try:
        persisted = await persistence_service.persist(
            db_session,
            event,
        )

        assert persisted.event_id == event.event_id
        assert persisted.event_type == event.event_type
        assert persisted.source_article_ids == event.source_article_ids

        retrieved = await persistence_service.get(
            db_session,
            event.event_id,
        )

        assert retrieved == persisted

        listed = await persistence_service.list(
            db_session,
            event_type=EventType.MONETARY_POLICY.value,
            catalyst=EventCatalyst.RATE_CUT.value,
            market_relevance=MarketRelevance.HIGH.value,
            impact_direction=ImpactDirection.POSITIVE.value,
        )

        matching = [item for item in listed if item.event_id == event.event_id]

        assert matching == [event]
    finally:
        await cleanup_events(
            db_session,
            [event.event_id],
        )


async def test_persist_is_idempotent_for_same_source_and_classification(
    db_session,
) -> None:
    """Reuse the original persisted event for the same source/classification."""

    source_article_id = uuid4()
    first_event = build_event(
        source_article_id=source_article_id,
    )
    second_event = first_event.model_copy(
        update={"event_id": uuid4()},
    )

    try:
        first = await persistence_service.persist(
            db_session,
            first_event,
        )
        second = await persistence_service.persist(
            db_session,
            second_event,
        )

        assert first.event_id == first_event.event_id
        assert second.event_id == first_event.event_id

        stored = await db_session.scalars(
            select(EventRecord).where(
                EventRecord.id == first_event.event_id,
            ),
        )

        assert len(list(stored)) == 1
    finally:
        await cleanup_events(
            db_session,
            [first_event.event_id],
        )


async def test_event_time_filter_is_applied(db_session) -> None:
    """Return only events inside the requested time range."""

    base_time = datetime.now(UTC).replace(microsecond=0)

    early = build_event(
        first_seen_at=base_time,
    )
    late = build_event(
        first_seen_at=base_time + timedelta(hours=12),
    )

    try:
        await persistence_service.persist(
            db_session,
            early,
        )
        await persistence_service.persist(
            db_session,
            late,
        )

        events = await persistence_service.list(
            db_session,
            start_at=base_time + timedelta(hours=6),
            end_at=base_time + timedelta(hours=18),
        )

        assert [event.event_id for event in events] == [late.event_id]
    finally:
        await cleanup_events(
            db_session,
            [early.event_id, late.event_id],
        )


async def test_invalid_time_range_is_rejected(db_session) -> None:
    """Reject a reversed event time range."""

    start = datetime(
        2027,
        9,
        19,
        tzinfo=UTC,
    )
    end = datetime(
        2027,
        9,
        18,
        tzinfo=UTC,
    )

    try:
        await persistence_service.list(
            db_session,
            start_at=start,
            end_at=end,
        )
    except ValueError as exc:
        assert str(exc) == "start_at must be earlier than end_at"
    else:
        raise AssertionError("Expected reversed time range to be rejected.")


async def test_missing_event_raises_domain_error(db_session) -> None:
    """Raise a domain error when an event does not exist."""

    missing_id = uuid4()

    try:
        await persistence_service.get(
            db_session,
            missing_id,
        )
    except EventNotFoundError as exc:
        assert str(missing_id) in str(exc)
    else:
        raise AssertionError("Expected EventNotFoundError.")
