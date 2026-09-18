from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.company_impact.models import (
    CompanyImpact,
    CompanyImpactDirection,
    ImpactType,
)
from app.company_impact.persistence import CompanyImpactPersistenceService
from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.market_impact import MarketImpactRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.market_impact.persistence import (
    MarketImpactNotFoundError,
    MarketImpactPersistenceService,
)
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event(
    *,
    company_name: str = "NVIDIA",
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
        affected_entities=(company_name,),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def make_company_impact(event: MarketEvent) -> CompanyImpact:
    return CompanyImpact(
        event_id=event.event_id,
        company_name=event.affected_entities[0],
        ticker="NVDA",
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.NEGATIVE,
        mechanism="Potential exposure through tariffs and market access.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The company is directly associated with the event.",
    )


def make_market_impact(event: MarketEvent) -> MarketImpact:
    return MarketImpact(
        event_id=event.event_id,
        company_name=event.affected_entities[0],
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.NEGATIVE,
        factor=ImpactFactor.MARKET_ACCESS,
        time_horizon=TimeHorizon.MEDIUM_TERM,
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The market access channel is the primary transmission factor.",
    )


async def cleanup(
    db_session,
    event_ids: list[UUID],
) -> None:
    await db_session.execute(
        delete(MarketImpactRecord).where(
            MarketImpactRecord.event_id.in_(event_ids),
        ),
    )
    await db_session.execute(
        delete(CompanyImpactRecord).where(
            CompanyImpactRecord.event_id.in_(event_ids),
        ),
    )
    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id.in_(event_ids),
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_persist_get_and_list_market_impact(db_session) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    company_impact = make_company_impact(event)
    company_record = await CompanyImpactPersistenceService().persist(
        db_session,
        company_impact,
    )

    company_impact_id = await db_session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == event.event_id,
            CompanyImpactRecord.company_name == event.affected_entities[0],
        ),
    )

    assert company_impact_id is not None

    market_impact = make_market_impact(event)
    service = MarketImpactPersistenceService()

    persisted = await service.persist(
        db_session,
        market_impact,
        company_impact_id,
    )

    record_id = await db_session.scalar(
        select(MarketImpactRecord.id).where(
            MarketImpactRecord.company_impact_id == company_impact_id,
        ),
    )

    assert record_id is not None

    retrieved = await service.get(
        db_session,
        record_id,
    )

    listed = await service.list(
        db_session,
        company_name=event.affected_entities[0],
        factor=ImpactFactor.MARKET_ACCESS.value,
    )

    assert persisted == market_impact
    assert retrieved == persisted
    assert listed == ((record_id, persisted),)
    assert company_record.company_name == "NVIDIA"

    await cleanup(
        db_session,
        [event.event_id],
    )


@pytest.mark.asyncio
async def test_persist_is_idempotent(db_session) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    company_record = await CompanyImpactPersistenceService().persist(
        db_session,
        make_company_impact(event),
    )

    company_impact_id = await db_session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == event.event_id,
        ),
    )

    assert company_impact_id is not None

    service = MarketImpactPersistenceService()
    market_impact = make_market_impact(event)

    first = await service.persist(
        db_session,
        market_impact,
        company_impact_id,
    )
    second = await service.persist(
        db_session,
        market_impact,
        company_impact_id,
    )

    records = (
        (
            await db_session.execute(
                select(MarketImpactRecord).where(
                    MarketImpactRecord.company_impact_id == company_impact_id,
                ),
            )
        )
        .scalars()
        .all()
    )

    assert first == second
    assert len(records) == 1
    assert company_record.event_id == event.event_id

    await cleanup(
        db_session,
        [event.event_id],
    )


@pytest.mark.asyncio
async def test_list_supports_event_time_filter(db_session) -> None:
    base_time = datetime.now(UTC).replace(microsecond=0)

    early_event = make_event(
        company_name="Apple",
        first_seen_at=base_time,
    )
    late_event = make_event(
        company_name="Microsoft",
        first_seen_at=base_time + timedelta(hours=12),
    )

    event_service = EventPersistenceService()

    await event_service.persist(db_session, early_event)
    await event_service.persist(db_session, late_event)

    company_service = CompanyImpactPersistenceService()

    await company_service.persist(
        db_session,
        make_company_impact(early_event),
    )
    await company_service.persist(
        db_session,
        make_company_impact(late_event),
    )

    company_records = (
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

    market_service = MarketImpactPersistenceService()

    early_impact = make_market_impact(early_event)
    late_impact = make_market_impact(late_event)

    early_company_impact_id = next(
        record.id
        for record in company_records
        if record.event_id == early_event.event_id
    )
    late_company_impact_id = next(
        record.id
        for record in company_records
        if record.event_id == late_event.event_id
    )

    await market_service.persist(
        db_session,
        early_impact,
        early_company_impact_id,
    )
    persisted_late = await market_service.persist(
        db_session,
        late_impact,
        late_company_impact_id,
    )

    listed = await market_service.list(
        db_session,
        start_at=base_time + timedelta(hours=6),
        end_at=base_time + timedelta(hours=18),
    )

    assert listed == (
        (
            next(
                record.id
                for record in (
                    await db_session.execute(
                        select(MarketImpactRecord).where(
                            MarketImpactRecord.company_impact_id
                            == late_company_impact_id,
                        ),
                    )
                )
                .scalars()
                .all()
            ),
            persisted_late,
        ),
    )

    await cleanup(
        db_session,
        [early_event.event_id, late_event.event_id],
    )


@pytest.mark.asyncio
async def test_invalid_time_range_is_rejected(db_session) -> None:
    service = MarketImpactPersistenceService()

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
async def test_missing_market_impact_raises(db_session) -> None:
    service = MarketImpactPersistenceService()

    with pytest.raises(
        MarketImpactNotFoundError,
        match="was not found",
    ):
        await service.get(
            db_session,
            uuid4(),
        )
