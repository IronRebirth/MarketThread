from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
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
from app.db.models.recommendation_provenance import (
    RecommendationProvenanceRecord,
)
from app.db.models.signal import SignalRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.main import app
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.market_impact.persistence import MarketImpactPersistenceService
from app.news.intelligence.models import ImpactDirection, MarketRelevance
from app.signals.persistence import SignalPersistenceService
from app.signals.service import SignalIntelligenceService


def make_event() -> MarketEvent:
    timestamp = datetime.now(UTC).replace(microsecond=0)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.TRADE_POLICY,
        title="Recommendation API test event",
        summary="A test event used for recommendation API coverage.",
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
    signal_id: UUID,
    instrument_id: UUID,
) -> None:
    await db_session.execute(
        delete(RecommendationProvenanceRecord).where(
            RecommendationProvenanceRecord.signal_id == signal_id,
        ),
    )
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
async def test_generate_get_list_and_provenance_recommendations(
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
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/recommendations/from-signal/{signal_id}",
            )

            assert response.status_code == 201

            payload = response.json()

            assert payload["signal_id"] == str(signal_id)
            assert payload["event_id"] == str(event.event_id)
            assert payload["company_name"] == "Test Company"
            assert payload["ticker"] == ticker
            assert payload["state"] == "consider"
            assert payload["confidence_score"] == 0.84
            assert payload["risk_score"] == 0.16

            recommendation_id = UUID(payload["recommendation_id"])

            get_response = await client.get(
                f"/recommendations/{recommendation_id}",
            )

            assert get_response.status_code == 200
            assert get_response.json()["recommendation_id"] == str(
                recommendation_id,
            )

            provenance_response = await client.get(
                f"/recommendations/{recommendation_id}/provenance",
            )

            assert provenance_response.status_code == 200

            provenance = provenance_response.json()

            assert provenance["recommendation_id"] == str(
                recommendation_id,
            )
            assert provenance["signal_id"] == str(signal_id)
            assert provenance["event_id"] == str(event.event_id)
            assert provenance["ruleset_version"] == "1.0.0"
            assert str(signal_id) in provenance["input_ids"]
            assert str(event.event_id) in provenance["input_ids"]
            assert provenance["evidence_article_ids"]
            assert provenance["assumptions"]
            assert provenance["invalidation_conditions"]

            list_response = await client.get(
                "/recommendations",
                params={
                    "signal_id": str(signal_id),
                    "ticker": ticker,
                    "state": "consider",
                },
            )

            assert list_response.status_code == 200
            assert len(list_response.json()) == 1
    finally:
        await cleanup(
            db_session,
            event.event_id,
            signal_id,
            instrument_id,
        )


@pytest.mark.asyncio
async def test_generate_recommendation_is_idempotent_with_provenance(
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
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first_response = await client.post(
                f"/recommendations/from-signal/{signal_id}",
            )
            second_response = await client.post(
                f"/recommendations/from-signal/{signal_id}",
            )

            assert first_response.status_code == 201
            assert second_response.status_code == 201
            assert first_response.json() == second_response.json()

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

            provenance_records = (
                (
                    await db_session.execute(
                        select(RecommendationProvenanceRecord).where(
                            RecommendationProvenanceRecord.signal_id == signal_id,
                        ),
                    )
                )
                .scalars()
                .all()
            )

            assert len(records) == 1
            assert len(provenance_records) == 1
    finally:
        await cleanup(
            db_session,
            event.event_id,
            signal_id,
            instrument_id,
        )


@pytest.mark.asyncio
async def test_missing_signal_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/recommendations/from-signal/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_recommendation_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/recommendations/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_recommendation_provenance_target_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/recommendations/{uuid4()}/provenance",
        )

    assert response.status_code == 404
