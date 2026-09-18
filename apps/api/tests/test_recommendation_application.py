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
from app.db.models.recommendation import RecommendationRecord
from app.db.models.signal import SignalRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.market_impact.persistence import MarketImpactPersistenceService
from app.news.intelligence.models import ImpactDirection, MarketRelevance
from app.recommendations.application import (
    RecommendationApplicationService,
    RecommendationMarketImpactRequiredError,
)
from app.signals.persistence import SignalPersistenceService
from app.signals.service import SignalIntelligenceService


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


async def build_persisted_signal(
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

    signal = SignalIntelligenceService().analyze(
        make_market_impact(event, ticker),
    )

    signal_record = await SignalPersistenceService().create(
        db_session,
        signal=signal,
        instrument_id=instrument.id,
        created_at=datetime.now(UTC),
        market_impact_id=market_impact_id,
    )

    return signal_record.id, instrument.id


async def cleanup(
    db_session,
    event_id: UUID,
    signal_id: UUID | None = None,
    instrument_id: UUID | None = None,
) -> None:
    if signal_id is not None:
        await db_session.execute(
            delete(RecommendationRecord).where(
                RecommendationRecord.signal_id == signal_id,
            ),
        )
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.id == signal_id,
            ),
        )

    if instrument_id is not None:
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
async def test_generates_recommendation_from_persisted_signal(
    db_session,
) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event = make_event()

    signal_id, instrument_id = await build_persisted_signal(
        db_session,
        event,
        ticker,
    )

    try:
        record = await RecommendationApplicationService().generate_from_signal(
            db_session,
            signal_id,
        )

        assert record.signal_id == signal_id
        assert record.event_id == event.event_id
        assert record.company_name == "Test Company"
        assert record.ticker == ticker
        assert record.state == "consider"
        assert record.confidence_score == 0.84
        assert record.risk_score == 0.16
        assert record.confidence_level == "high"
        assert record.risk_level == "low"
        assert record.evidence_article_ids
        assert record.assumptions
        assert "research-oriented" in record.rationale.lower()
    finally:
        await cleanup(
            db_session,
            event.event_id,
            signal_id,
            instrument_id,
        )


@pytest.mark.asyncio
async def test_recommendation_generation_is_idempotent(
    db_session,
) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event = make_event()

    signal_id, instrument_id = await build_persisted_signal(
        db_session,
        event,
        ticker,
    )

    try:
        service = RecommendationApplicationService()

        first = await service.generate_from_signal(
            db_session,
            signal_id,
        )
        second = await service.generate_from_signal(
            db_session,
            signal_id,
        )

        records = (
            (
                await db_session.execute(
                    select(RecommendationRecord).where(
                        RecommendationRecord.signal_id == signal_id,
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
            signal_id,
            instrument_id,
        )


@pytest.mark.asyncio
async def test_signal_without_market_impact_is_rejected(
    db_session,
) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    instrument = Instrument(
        symbol=f"TST{uuid4().hex[:8].upper()}",
        name="Test Company",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)

    signal = SignalIntelligenceService().analyze(
        make_market_impact(event, instrument.symbol),
    )

    signal_record = await SignalPersistenceService().create(
        db_session,
        signal=signal,
        instrument_id=instrument.id,
        created_at=datetime.now(UTC),
    )

    try:
        with pytest.raises(
            RecommendationMarketImpactRequiredError,
            match="linked to a persisted market impact",
        ):
            await RecommendationApplicationService().generate_from_signal(
                db_session,
                signal_record.id,
            )
    finally:
        await db_session.execute(
            delete(SignalRecord).where(
                SignalRecord.id == signal_record.id,
            ),
        )
        await db_session.execute(
            delete(Instrument).where(
                Instrument.id == instrument.id,
            ),
        )
        await db_session.execute(
            delete(EventRecord).where(
                EventRecord.id == event.event_id,
            ),
        )
        await db_session.commit()
