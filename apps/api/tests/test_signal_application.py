from datetime import UTC, datetime
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
from app.db.models.instrument import Instrument
from app.db.models.market_impact import MarketImpactRecord
from app.db.models.signal import SignalRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.market_impact.persistence import MarketImpactPersistenceService
from app.news.intelligence.models import ImpactDirection, MarketRelevance
from app.signals.application import (
    SignalApplicationService,
    SignalInstrumentNotFoundError,
)


def make_event() -> MarketEvent:
    timestamp = datetime.now(UTC).replace(microsecond=0)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.TRADE_POLICY,
        title="Test semiconductor trade event",
        summary="A test event affecting a listed company.",
        catalyst=EventCatalyst.TARIFF,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.POSITIVE,
        affected_entities=("Test Company",),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def make_company_impact(
    event: MarketEvent,
    ticker: str,
) -> CompanyImpact:
    return CompanyImpact(
        event_id=event.event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.POSITIVE,
        mechanism="Potential exposure through market access.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The company is directly associated with the event.",
    )


def make_market_impact(
    event: MarketEvent,
    ticker: str,
) -> MarketImpact:
    return MarketImpact(
        event_id=event.event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.POSITIVE,
        factor=ImpactFactor.MARKET_ACCESS,
        time_horizon=TimeHorizon.MEDIUM_TERM,
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="Market access is the primary transmission factor.",
    )


async def persist_pipeline(
    db_session,
    event: MarketEvent,
    ticker: str,
) -> tuple[UUID, UUID]:
    await EventPersistenceService().persist(
        db_session,
        event,
    )

    await CompanyImpactPersistenceService().persist(
        db_session,
        make_company_impact(event, ticker),
    )

    company_impact_id = await db_session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == event.event_id,
        ),
    )

    assert company_impact_id is not None

    await MarketImpactPersistenceService().persist(
        db_session,
        make_market_impact(event, ticker),
        company_impact_id,
    )

    market_impact_id = await db_session.scalar(
        select(MarketImpactRecord.id).where(
            MarketImpactRecord.company_impact_id == company_impact_id,
        ),
    )

    assert market_impact_id is not None

    return company_impact_id, market_impact_id


async def cleanup(
    db_session,
    event_id: UUID,
    instrument_id: UUID | None = None,
) -> None:
    if instrument_id is not None:
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.instrument_id == instrument_id,
            ),
        )
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id == instrument_id,
            ),
        )

    await db_session.execute(
        delete(MarketImpactRecord).where(
            MarketImpactRecord.event_id == event_id,
        ),
    )
    await db_session.execute(
        delete(CompanyImpactRecord).where(
            CompanyImpactRecord.event_id == event_id,
        ),
    )
    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id == event_id,
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_generates_signal_from_persisted_market_impact(
    db_session,
) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event = make_event()

    _, market_impact_id = await persist_pipeline(
        db_session,
        event,
        ticker,
    )

    instrument = Instrument(
        symbol=ticker,
        name="Test Company",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    try:
        record = await SignalApplicationService().generate_from_market_impact(
            db_session,
            market_impact_id,
        )

        assert record.market_impact_id == market_impact_id
        assert record.instrument_id == instrument.id
        assert record.event_id == event.event_id
        assert record.company_name == "Test Company"
        assert record.ticker == ticker
        assert record.direction == "positive"
        assert record.strength == "strong"
        assert record.opportunity == "opportunity"
        assert record.confidence == 0.84
    finally:
        await cleanup(
            db_session,
            event.event_id,
            instrument.id,
        )


@pytest.mark.asyncio
async def test_generation_is_idempotent(
    db_session,
) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event = make_event()

    _, market_impact_id = await persist_pipeline(
        db_session,
        event,
        ticker,
    )

    instrument = Instrument(
        symbol=ticker,
        name="Test Company",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    try:
        service = SignalApplicationService()

        first = await service.generate_from_market_impact(
            db_session,
            market_impact_id,
        )
        second = await service.generate_from_market_impact(
            db_session,
            market_impact_id,
        )

        records = (
            (
                await db_session.execute(
                    select(SignalRecord).where(
                        SignalRecord.market_impact_id == market_impact_id,
                    ),
                )
            )
            .scalars()
            .all()
        )

        assert first.id == second.id
        assert len(records) == 1
    finally:
        await cleanup(
            db_session,
            event.event_id,
            instrument.id,
        )


@pytest.mark.asyncio
async def test_missing_instrument_is_rejected(db_session) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event = make_event()

    _, market_impact_id = await persist_pipeline(
        db_session,
        event,
        ticker,
    )

    try:
        with pytest.raises(
            SignalInstrumentNotFoundError,
            match="No active persisted instrument",
        ):
            await SignalApplicationService().generate_from_market_impact(
                db_session,
                market_impact_id,
            )
    finally:
        await cleanup(
            db_session,
            event.event_id,
        )
