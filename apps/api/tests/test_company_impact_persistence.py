from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.company_impact.models import (
    CompanyImpact,
    CompanyImpactDirection,
    ImpactType,
)
from app.company_impact.persistence import (
    CompanyImpactNotFoundError,
    CompanyImpactPersistenceService,
)
from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event(
    *,
    company_names: tuple[str, ...] = ("NVIDIA",),
    first_seen_at: datetime | None = None,
) -> MarketEvent:
    timestamp = first_seen_at or datetime.now(UTC)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.TRADE_POLICY,
        title="New semiconductor trade restrictions announced",
        summary="New trade restrictions affect the semiconductor industry.",
        catalyst=EventCatalyst.TARIFF,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.NEGATIVE,
        affected_entities=company_names,
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def make_impact(event: MarketEvent, company_name: str) -> CompanyImpact:
    return CompanyImpact(
        event_id=event.event_id,
        company_name=company_name,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.NEGATIVE,
        mechanism="Potential exposure through tariffs and market access.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale=f"{company_name} is directly associated with the event.",
    )


async def cleanup(
    db_session,
    event_ids: list[UUID],
    impact_ids: list[UUID],
) -> None:
    if impact_ids:
        await db_session.execute(
            delete(CompanyImpactRecord).where(
                CompanyImpactRecord.id.in_(impact_ids),
            ),
        )

    if event_ids:
        await db_session.execute(
            delete(EventRecord).where(
                EventRecord.id.in_(event_ids),
            ),
        )

    await db_session.commit()


@pytest.mark.asyncio
async def test_persist_get_and_list_company_impact(db_session) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    service = CompanyImpactPersistenceService()
    impact = make_impact(event, "NVIDIA")

    persisted = await service.persist(
        db_session,
        impact,
    )

    impact_id = await db_session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == event.event_id,
            CompanyImpactRecord.company_name == "NVIDIA",
            CompanyImpactRecord.impact_type == "direct",
        ),
    )

    assert impact_id is not None

    retrieved = await service.get(
        db_session,
        impact_id,
    )

    listed = await service.list(
        db_session,
        company_name="NVIDIA",
        impact_type=ImpactType.DIRECT.value,
    )

    assert persisted.company_name == "NVIDIA"
    assert retrieved == persisted
    assert listed == (persisted,)

    await cleanup(
        db_session,
        [event.event_id],
        [impact_id],
    )


@pytest.mark.asyncio
async def test_persist_is_idempotent(db_session) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    impact = make_impact(event, "NVIDIA")
    service = CompanyImpactPersistenceService()

    first = await service.persist(
        db_session,
        impact,
    )
    second = await service.persist(
        db_session,
        impact,
    )

    records = (
        (
            await db_session.execute(
                select(CompanyImpactRecord).where(
                    CompanyImpactRecord.event_id == event.event_id,
                ),
            )
        )
        .scalars()
        .all()
    )

    assert first == second
    assert len(records) == 1

    await cleanup(
        db_session,
        [event.event_id],
        [records[0].id],
    )


@pytest.mark.asyncio
async def test_list_supports_event_time_filter(db_session) -> None:
    base_time = datetime.now(UTC).replace(microsecond=0)

    early_event = make_event(
        company_names=("Apple",),
        first_seen_at=base_time,
    )
    late_event = make_event(
        company_names=("Microsoft",),
        first_seen_at=base_time + timedelta(hours=12),
    )

    event_service = EventPersistenceService()

    await event_service.persist(
        db_session,
        early_event,
    )
    await event_service.persist(
        db_session,
        late_event,
    )

    company_service = CompanyImpactPersistenceService()

    persisted_early = await company_service.persist(
        db_session,
        make_impact(early_event, "Apple"),
    )
    persisted_late = await company_service.persist(
        db_session,
        make_impact(late_event, "Microsoft"),
    )

    listed = await company_service.list(
        db_session,
        start_at=base_time + timedelta(hours=6),
        end_at=base_time + timedelta(hours=18),
    )

    assert listed == (persisted_late,)
    assert persisted_early != persisted_late

    records = (
        (
            await db_session.execute(
                select(CompanyImpactRecord).where(
                    CompanyImpactRecord.event_id.in_(
                        [early_event.event_id, late_event.event_id],
                    ),
                ),
            )
        )
        .scalars()
        .all()
    )

    await cleanup(
        db_session,
        [early_event.event_id, late_event.event_id],
        [record.id for record in records],
    )


@pytest.mark.asyncio
async def test_invalid_time_range_is_rejected(db_session) -> None:
    service = CompanyImpactPersistenceService()

    with pytest.raises(
        ValueError,
        match="start_at must be earlier than end_at",
    ):
        await service.list(
            db_session,
            start_at=datetime(2027, 1, 2, tzinfo=UTC),
            end_at=datetime(2027, 1, 1, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_missing_company_impact_raises(db_session) -> None:
    service = CompanyImpactPersistenceService()

    with pytest.raises(
        CompanyImpactNotFoundError,
        match="was not found",
    ):
        await service.get(
            db_session,
            uuid4(),
        )
