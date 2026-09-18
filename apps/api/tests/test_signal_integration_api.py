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


def make_event() -> MarketEvent:
    timestamp = datetime.now(UTC).replace(microsecond=0)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.EARNINGS,
        title="Test earnings event",
        summary="A test earnings event for signal integration.",
        catalyst=EventCatalyst.EARNINGS_SURPRISE,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.POSITIVE,
        affected_entities=("Test Company",),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


async def create_market_impact(
    db_session,
    ticker: str | None = None,
) -> tuple[UUID, UUID]:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    company_impact = CompanyImpact(
        event_id=event.event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.POSITIVE,
        mechanism="Potential exposure through earnings.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The company is directly associated with the event.",
    )

    await CompanyImpactPersistenceService().persist(
        db_session,
        company_impact,
    )

    company_impact_id = await db_session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == event.event_id,
        ),
    )

    assert company_impact_id is not None

    market_impact = MarketImpact(
        event_id=event.event_id,
        company_name="Test Company",
        ticker=ticker,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.POSITIVE,
        factor=ImpactFactor.REVENUE,
        time_horizon=TimeHorizon.SHORT_TERM,
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="Revenue is the primary transmission factor.",
    )

    await MarketImpactPersistenceService().persist(
        db_session,
        market_impact,
        company_impact_id,
    )

    market_impact_id = await db_session.scalar(
        select(MarketImpactRecord.id).where(
            MarketImpactRecord.company_impact_id == company_impact_id,
        ),
    )

    assert market_impact_id is not None

    return event.event_id, market_impact_id


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
async def test_generate_signal_from_market_impact(
    client,
    db_session,
) -> None:
    ticker = f"TST{uuid4().hex[:8].upper()}"
    event_id, market_impact_id = await create_market_impact(
        db_session,
        ticker=ticker,
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
        response = await client.post(
            f"/signals/from-market-impact/{market_impact_id}",
        )

        assert response.status_code == 201

        payload = response.json()

        assert payload["instrument_id"] == str(instrument.id)
        assert payload["event_id"] == str(event_id)
        assert payload["company_name"] == "Test Company"
        assert payload["ticker"] == ticker
        assert payload["direction"] == "positive"
        assert payload["strength"] == "strong"
        assert payload["opportunity"] == "opportunity"
        assert payload["confidence"] == 0.84

    finally:
        await cleanup(
            db_session,
            event_id,
            instrument.id,
        )


@pytest.mark.asyncio
async def test_missing_market_impact_returns_404(client) -> None:
    response = await client.post(
        f"/signals/from-market-impact/{uuid4()}",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_instrument_returns_404(
    client,
    db_session,
) -> None:
    event_id, market_impact_id = await create_market_impact(
        db_session,
        ticker=f"TST{uuid4().hex[:8].upper()}",
    )

    try:
        response = await client.post(
            f"/signals/from-market-impact/{market_impact_id}",
        )

        assert response.status_code == 404
        assert "No active persisted instrument" in response.json()["detail"]
    finally:
        await cleanup(
            db_session,
            event_id,
        )


@pytest.mark.asyncio
async def test_missing_ticker_returns_422(
    client,
    db_session,
) -> None:
    event_id, market_impact_id = await create_market_impact(
        db_session,
        ticker=None,
    )

    try:
        response = await client.post(
            f"/signals/from-market-impact/{market_impact_id}",
        )

        assert response.status_code == 422
        assert "requires a ticker" in response.json()["detail"]
    finally:
        await cleanup(
            db_session,
            event_id,
        )
